from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
import spacy

_NLP = None

def get_nlp():
    """Load and return the SpaCy NLP model for French."""

    global _NLP
    if _NLP is None:
        _NLP = spacy.load("fr_core_news_sm")
    return _NLP

@dataclass
class Fact:
    sent_text: str #texte brut de la phrase
    subj: Optional[str] #sujet de la phrase
    verb: Optional[str] #verbe de la phrase
    obj: Optional[str] #objet de la phrase
    adj_pairs: List[Tuple[str, str]] #liste de paires (nom, adjectif) associées dans la phrase

def extract_facts(text: str) -> List[Fact]:
    """Extract facts from the given text using SpaCy NLP."""

    nlp = get_nlp()
    doc = nlp(text)
    facts: List[Fact] = []
    for sent in doc.sents:
        subj = None
        verb = None
        obj = None
        adj_pairs: List[Tuple[str, str]] = []

        # 1) verbe principal = ROOT
        root = None
        for token in sent:
            if token.dep_ == "ROOT":
                root = token
                break

        if root is not None:
            verb = root.lemma_ #forme canonique du verbe, + stable

            # 2) sujet / objet parmi les enfants du ROOT
            for child in root.children:
                if child.dep_ in ("nsubj", "nsubj:pass") and subj is None:
                    subj = child.text
                elif child.dep_ in ("obj", "iobj") and obj is None:
                    obj = child.text

            # 3) adjectifs liés à des noms dans la phrase
            for token in sent:
                if token.dep_ == "amod" and token.head.pos_ in ("NOUN","PROPN"):
                    adj_pairs.append((token.head.text, token.text))

            facts.append(Fact(
                sent_text=sent.text.strip(),
                subj=subj,
                verb=verb,
                obj=obj,
                adj_pairs=adj_pairs
            ))

    return facts