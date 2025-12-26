from __future__ import annotations

from enum import Enum
import random

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

# Predefined pools of words for generating distractors

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


POOLS = {
    "animals": ANIMALS,
    "people": PEOPLE,
    "colors": COLORS,
}

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
