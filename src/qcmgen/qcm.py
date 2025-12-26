from __future__ import annotations

from enum import Enum
import random
from typing import Callable, Dict
from qcmgen.nlp import Fact


class QuestionType(str, Enum):
    """
    Stable identifiers for the different question templates we support.
    Using str+Enum makes it JSON/log-friendly and easy to display in the UI.
    """
    OBJECT = "object"         # "Que {verb} {subj} ?"
    SUBJECT = "subject"       # "Qui {verb} {obj} ?"
    ADJ_NOUN = "adj_noun"     # "Quel animal est {adj} ?"
    ADJ_SUBJECT = "adj_subj"  # "Qui est {adj} ?"

QUESTION_SPECS = {
    QuestionType.OBJECT: {
        "template": "Que {verb} {subj} ?",
        "required": ("subj", "verb", "obj"),
        "pool": "animals",   # v0 default
    },
    QuestionType.SUBJECT: {
        "template": "Qui {verb} {obj} ?",
        "required": ("subj", "verb", "obj"),
        "pool": "people",
    },
    QuestionType.ADJ_NOUN: {
        "template": "Quel animal est {adj} ?",
        "required": ("adj_pairs",),
        "pool": "animals",
    },
    QuestionType.ADJ_SUBJECT: {
        "template": "Qui est {adj} ?",
        "required": ("subj", "adj"),
        "pool": "people",
    },
}

from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class QCM:
    question: str
    choices: List[str]
    answer_index: int
    qtype: QuestionType
    rationale: Optional[str] = None

from typing import Dict

# Payload qui gère les infos nécessaires à la génération d'un QCM
@dataclass(frozen=True)
class QcmPayload:
    qtype: QuestionType
    template: str
    template_vars: Dict[str, str]
    correct: str
    pool_name: str
    rationale: str = ""

# Pools de distracteurs pour 3 différentes catégories (v0)

ANIMALS = [
    "chat", "chien", "souris", "lapin", "cheval", "lion", "poisson",
    "oiseau", "vache", "mouton", "cochon", "éléphant"
]

PEOPLE = [
    "Martin", "Marie", "Paul", "Lina", "Sami", "Emma", "Noah"
]

COLORS = [
    "gris", "rouge", "bleu", "vert", "jaune", "noir", "blanc", "orange", "rose"
]

def _pluralize_animal(word: str) -> str:
    exceptions = {
        "cheval": "chevaux",
        "animal": "animaux",
    }
    if word in exceptions:
        return exceptions[word]
    if word.endswith(("s", "x", "z")):
        return word
    return word + "s"

POOLS = {
    "animals": ANIMALS,
    "people": PEOPLE,
    "colors": COLORS,
}

ANIMALS_PLUR = [_pluralize_animal(a) for a in ANIMALS]
POOLS["animals_plur"] = ANIMALS_PLUR


def build_choices(correct: str, pool_name: str, k: int = 3):
    """Build a list of k+1 choices including the correct answer and k distractors from the specified pool."""
    pool = POOLS[pool_name]
    pool_clean = [x for x in pool if x.lower() != correct.lower()]

    if len(pool_clean) >= k:
        distractors = random.sample(pool_clean, k)
    else:
        distractors = pool_clean

    choices = distractors + [correct]
    random.shuffle(choices)
    answer_index = choices.index(correct)
    return choices, answer_index

def _normalize_answer(s: str) -> str:
    return " ".join(s.strip().split())

def payload_to_qcm(payload: QcmPayload) -> QCM:
    question = payload.template.format(**payload.template_vars) #remplir les variables du template (ex : "Que {verb} {subj} ?".format(verb="voir", subj="Martin") => "Que voir Martin ?") 

    correct = _normalize_answer(payload.correct)
    choices, answer_index = build_choices(correct, pool_name=payload.pool_name, k=3)

    return QCM(
        question=question,
        choices=choices,
        answer_index=answer_index,
        qtype=payload.qtype,
        rationale=payload.rationale
    )   

# Fonctions d'expansion pour chaque type de question

ExpandFn = Callable[[Fact], List[QcmPayload]] # Type alias pour les fonctions d'expansion

def _expand_object(fact: Fact) -> List[QcmPayload]:
    """Generate OBJECT question payloads from a Fact."""
    if not (fact.subj and fact.verb_text and fact.obj_phrase and fact.obj_head):
        return []
    
    spec = QUESTION_SPECS[QuestionType.OBJECT]
    return [QcmPayload(
        qtype=QuestionType.OBJECT,
        template=spec["template"],
        template_vars={
            "verb": fact.verb_text,
            "subj": fact.subj
        },
        correct=fact.obj_head,
        pool_name=spec["pool"],
        rationale=f"OBJECT from subj+verb+obj: {fact.sent_text} "
    )]

def _expand_subject(fact: Fact) -> List[QcmPayload]:
    if not (fact.subj and fact.verb_text and fact.obj_phrase):
        return []

    spec = QUESTION_SPECS[QuestionType.SUBJECT]
    return [
        QcmPayload(
            qtype=QuestionType.SUBJECT,
            template=spec["template"],
            template_vars={"verb": fact.verb_text, "obj": fact.obj_phrase},
            correct=fact.subj,
            pool_name=spec["pool"],
            rationale="SUBJECT from subj+verb+obj",
        )
    ]

def _expand_adj_noun(fact: Fact) -> List[QcmPayload]:
    if not fact.adj_pairs:
        return []

    spec = QUESTION_SPECS[QuestionType.ADJ_NOUN]
    payloads: List[QcmPayload] = []

    for noun, adj, number in fact.adj_pairs:
        payloads.append(
            QcmPayload(
                qtype=QuestionType.ADJ_NOUN,
                template=spec["template"] if number != "Plur" else "Quels animaux sont {adj} ?",
                template_vars={"adj": adj},
                correct=noun,
                pool_name=spec["pool"] if number != "Plur" else "animals_plur", #assuming its animals for now
                rationale=f"ADJ_NOUN from pair noun={noun} adj={adj}",
            )
        )

    return payloads

EXPANDERS: Dict[QuestionType, ExpandFn] = {
    QuestionType.OBJECT: _expand_object,
    QuestionType.SUBJECT: _expand_subject,
    QuestionType.ADJ_NOUN: _expand_adj_noun,
}

def generate_payloads(fact: Fact) -> List[QcmPayload]:
    """Generate QcmPayloads from a Fact using all applicable expanders.
    How it worlks: itère sur tous les types de questions définis dans EXPANDERS,
    applique chaque fonction d'expansion au fact donné, et collecte tous les
    payloads générés. Ensuite, il déduplique les payloads pour éviter les
    doublons.
    """

    payloads: List[QcmPayload] = []

    for qtype, expander in EXPANDERS.items():
        payloads.extend(expander(fact))

    # Déduplication simple
    seen = set()
    unique_payloads = []
    for payload in payloads:
        key = (payload.qtype, tuple(sorted(payload.template_vars.items())), payload.correct)
        if key not in seen:
            seen.add(key)
            unique_payloads.append(payload)

    return unique_payloads

def generate_qcms(fact: Fact, max_qcms: int = 6) -> List[QCM]:
    payloads = generate_payloads(fact)
    qcms = [payload_to_qcm(p) for p in payloads]
    return qcms[:max_qcms]

