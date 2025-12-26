from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
import spacy
from spacy.tokens import Span, Token


_NLP = None

def get_nlp():
    """Load and return the SpaCy NLP model for French."""

    global _NLP
    if _NLP is None:
        _NLP = spacy.load("fr_core_news_md")
    return _NLP

@dataclass
class Fact:
    sent_text: str #texte brut de la phrase
    subj: Optional[str] #sujet de la phrase
    verb_lemma: Optional[str] #verbe de la phrase ex: "manger"
    verb_text: Optional[str] #forme conjuguée du verbe dans la phrase ex: "a mangé"
    obj_phrase: Optional[str] #groupe nominal objet complet de la phrase ex: "le ballon rouge"
    obj_head: Optional[str] #nom principal de l'objet ex: "ballon"
    adj_pairs: List[Tuple[str, str]] #liste de paires (nom, adjectif) associées dans la phrase

def extract_facts(text: str) -> List[Fact]:
    """Extract facts from the given text using SpaCy NLP."""

    nlp = get_nlp()
    doc = nlp(text)
    facts: List[Fact] = []
    for sent in doc.sents:
        subj = None
        verb_lemma = None
        verb_text = None
        obj_phrase = None
        obj_head = None
        adj_pairs: List[Tuple[str, str, str]] = []  # (noun_text, adj_text, number="Sing"/"Plur"/"")

        # 1) verbe principal = ROOT
        root = robust_root_extraction(sent)

        if root is not None:
            verb_lemma = root.lemma_ #forme canonique du verbe, + stable

            # vers_text: root + auxiliaires (passé composé, etc)
            parts = [root]
            for child in root.children:
                if child.dep_ in ("aux", "aux:pass", "aux:tense"):
                    parts.insert(0, child)

            # garder l'ordre des tokens dans la phrase
            parts = sorted(parts, key=lambda t: t.i)
            verb_text = " ".join(t.text for t in parts)

            # 2) sujet (robuste) + objet parmi les enfants du ROOT
            subj = robust_subj_extraction(sent)

            for child in root.children:
                if child.dep_ in ("obj", "iobj") and obj_phrase is None:
                    obj_phrase = " ".join(t.text for t in child.subtree) #gérer les objets composés (ex: "le ballon rouge" plutot que "ballon")
                    obj_head = child.text

            # 3) adjectifs liés à des noms dans la phrase
            for token in sent:
                if token.dep_ == "amod" and token.head.pos_ in ("NOUN", "PROPN"):
                    head = token.head
                    nums = head.morph.get("Number")
                    number = nums[0] if nums else ""
                    adj_pairs.append((head.text, token.text, number))

            facts.append(Fact(
                sent_text=sent.text.strip(),
                subj=subj,
                verb_lemma=verb_lemma,
                verb_text=verb_text,
                obj_phrase=obj_phrase,
                obj_head=obj_head,
                adj_pairs=adj_pairs
            ))

    return facts

def robust_subj_extraction(sent: Span) -> Optional[Token]:
    """Extract the subject of a sentence, with robustness to certain structures."""

    # choisir un sujet robuste
    subj = None
    for token in sent:
        if token.dep_ in ("nsubj", "nsubj:pass"):
            subj = " ".join(t.text for t in token.subtree) #gérer les sujets composés (ex: "son chien" plutot que "chien")
            break

    # si pas de sujet trouvé, fallback: premier NOUN ou PROPN
    if subj is None:
        for token in sent:
            if token.pos_ == "PROPN":
                subj = " ".join(t.text for t in token.subtree)
                break

    if subj is None:
        for token in sent:
            if token.pos_ == "NOUN":
                subj = " ".join(t.text for t in token.subtree)
                break

    return subj

def robust_root_extraction(sent: Span) -> Optional[Token]:
    """Extract the root verb of a sentence, with robustness to certain structures."""

    # choisir un verbe principal robuste
    root = None
    for token in sent:
        if token.dep_ == "ROOT":
            root = token
            break

    # si ROOT n'est pas un verbe, fallback: premier token VERB
    if root is None or root.pos_ not in ("VERB", "AUX"):
        for token in sent:
            if token.pos_ in ("VERB", "AUX"):
                root = token
                break

    return root
