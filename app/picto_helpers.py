import unicodedata
import streamlit as st
from qcmgen.pictos.resolve import resolve_term_to_picto_strict


def cleanup_term(term: str) -> str:
    """
    Cleanup term (remove accents, ..) to get better chances of a match on the arasaac database
    """
    term = term.strip().lower()

    # retire la ponctuation simple
    for ch in [".", ",", "?", "!", ":", ";", "…"]:
        term = term.replace(ch, "")

    # retire les articles en début de terme
    for prefix in ("le ", "la ", "les ", "un ", "une ", "des ", "l'"):
        if term.startswith(prefix):
            term = term[len(prefix):]

    # enlève les accents (é -> e, ç -> c, etc.)
    term = "".join(
        c for c in unicodedata.normalize("NFD", term)
        if unicodedata.category(c) != "Mn"
    )

    return term

def term_variants(term: str) -> list[str]:
    """
    Enlever les conjugaisons (heuristique)
    """
    base = cleanup_term(term)
    variants = {base}

    # singulier simple
    if base.endswith("s") and len(base) > 3:
        variants.add(base[:-1])

    # heuristiques de conjugaison (présent / imparfait / futur proche)
    for suffix in ("e", "es", "ent", "ons", "ez", "ais", "ait", "aient"):
        if base.endswith(suffix) and len(base) > len(suffix) + 2:
            stem = base[: -len(suffix)]
            variants.add(stem)
            variants.add(stem + "er")  # ex: mange -> manger
            variants.add(stem + "ir")
            variants.add(stem + "re")

    return list(variants)

def get_picto_with_variants(term: str, expected_type: str | None = None):
    """
    Loops on all possible variants, starting with the cleanup regular version, and returns the first match
    """
    for candidate in term_variants(term):
        url = get_picto_url(candidate, expected_type=expected_type)
        if url:
            return candidate, url
    return None, None

def get_picto_url(term: str, expected_type: str | None = None) -> str | None:
    """
    Fetch pictogram image url given the pictogram term
    """
    term_norm = term.strip().lower()
    if not term_norm:
        return None
    
    #term_norm = cleanup_term(term_norm)

    cache = st.session_state.picto_cache
    if term_norm in cache:
        return cache[term_norm]

    r = resolve_term_to_picto_strict(term_norm, lang="fr", expected_type=expected_type)
    url = r.url if r else None
    cache[term_norm] = url
    return url
