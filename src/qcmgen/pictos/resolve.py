## Done with ChatGPT

import json
import os
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

from qcmgen.pictos.arasaac_client import ArasaacClient

EXPECTED_TAGS = {
    "color": {"color", "colour"},
    "weather": {"weather", "meteorology", "rain", "sun", "cloud", "wind", "snow", "storm"},
    "drink": {"drink", "beverage"},
    "food": {"food", "feeding", "fruit", "vegetable", "dessert", "bread"},
    "place": {"place", "building", "house", "home", "school", "transport", "city"},
    # "object" : pas de contrainte forte (sinon tu vas jeter trop de choses)
}


@dataclass(frozen=True)
class ResolvedPicto:
    term: str
    picto_id: int
    url: str
    score: float
    tags: List[str]
    categories: List[str]
    keyword: Optional[str] = None
    plural: Optional[str] = None
    source: str = "arasaac"


def _strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_term(term: str) -> str:
    term = term.strip().lower()
    term = _strip_accents(term)
    term = " ".join(term.split())
    return term


def _naive_singularize_fr(term: str) -> str:
    # v0: suffisant pour "chats"->"chat". Ne pas sur-optimiser.
    if term.endswith("s") and len(term) > 3:
        return term[:-1]
    return term


def _extract_keywords(item: Dict[str, Any]) -> List[str]:
    """
    ARASAAC renvoie souvent un champ 'keywords' (liste), parfois sous forme:
    - [{'keyword': 'chat', 'type': ...}, ...]
    ou directement des strings selon versions.
    """
    kws = item.get("keywords", [])
    out: List[str] = []
    for x in kws:
        if isinstance(x, str):
            out.append(normalize_term(x))
        elif isinstance(x, dict) and "keyword" in x:
            out.append(normalize_term(str(x["keyword"])))
    return out


def _score_candidate(term_norm: str, cand: Dict[str, Any]) -> float:
    score = 0.0
    kws = _extract_keywords(cand)

    # Exact keyword match
    if term_norm in kws:
        score += 10.0

    # Substring match in any keyword
    if any(term_norm in kw for kw in kws):
        score += 3.0

    # Fallback: tiny score if has any keywords
    if kws:
        score += 0.5

    return score

def _cache_path(lang: str) -> str:
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / f"arasaac_cache_{lang}.json")



def _load_cache(lang: str) -> Dict[str, Any]:
    path = _cache_path(lang)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(lang: str, cache: Dict[str, Any]) -> None:
    path = _cache_path(lang)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def resolve_term_to_picto(term: str, lang: str = "fr", limit: int = 12, expected_type: str | None = None) -> Optional[ResolvedPicto]:
    """
    Resolve a term to the best ARASAAC pictogram candidate.
    Uses disk cache: data/arasaac_cache_{lang}.json
    """
    term_norm = normalize_term(term)
    if not term_norm:
        return None

    cache = _load_cache(lang)
    if term_norm in cache:
        hit = cache[term_norm]

        # Si ancienne entrée (pas de tags), on refetch pour enrichir
        if hit.get("tags") and hit.get("categories"):
            return ResolvedPicto(
                term=term,
                picto_id=int(hit["picto_id"]),
                url=str(hit["url"]),
                score=float(hit.get("score", 0.0)),
                tags=hit.get("tags", []) or [],
                categories=hit.get("categories", []) or [],
                keyword=hit.get("keyword"),
                plural=hit.get("plural"),
            )



    client = ArasaacClient(lang=lang)
    queries = [term_norm]
    sing = _naive_singularize_fr(term_norm)
    if sing != term_norm:
        queries.append(sing)

    best: Optional[Tuple[float, Dict[str, Any]]] = None

    for q in queries:
        results = client.search(q, limit=limit)
        for cand in results:
            s = _score_candidate(q, cand)
            if best is None or s > best[0]:
                best = (s, cand)

    if best is None:
        return None

    score, cand = best
    picto_id = int(cand.get("_id")) if cand.get("_id") is not None else None
    if picto_id is None:
        return None
    
    tags, categories = _extract_tags_categories(cand)
    kw, pl = _extract_keyword_info(cand)


    url = client.pictogram_url(picto_id)
    resolved = ResolvedPicto(
    term=term,
    picto_id=picto_id,
    url=url,
    score=score,
    tags=tags,
    categories=categories,
    keyword=kw,
    plural=pl,
)

    cache[term_norm] = {
        "picto_id": picto_id,
        "url": url,
        "score": score,
        "tags": tags,
        "categories": categories,
        "keyword": kw,
        "plural": pl,
    }
    print(f"Caching pictogram for term '{term_norm}' (picto_id={picto_id})")
    _save_cache(lang, cache)

    return resolved

def _extract_keyword_info(cand: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    kws = cand.get("keywords", []) or []
    for x in kws:
        if isinstance(x, dict) and "keyword" in x:
            kw = x.get("keyword")
            pl = x.get("plural")
            return (str(kw) if kw else None, str(pl) if pl else None)
    return (None, None)


def _extract_tags_categories(cand: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    tags = cand.get("tags", []) or []
    categories = cand.get("categories", []) or []
    tags_out = [str(t).strip().lower() for t in tags if str(t).strip()]
    cat_out = [str(c).strip().lower() for c in categories if str(c).strip()]
    return tags_out, cat_out

import random
from typing import Set


def sample_cached_by_tag(tag: str, k: int = 3, exclude_ids: Optional[Set[int]] = None, lang: str = "fr") -> List[ResolvedPicto]:
    tag = tag.strip().lower()
    exclude_ids = exclude_ids or set()

    cache = _load_cache(lang)
    candidates: List[ResolvedPicto] = []

    for term_norm, hit in cache.items():
        picto_id = int(hit.get("picto_id", -1))
        if picto_id in exclude_ids:
            continue

        tags = hit.get("tags", []) or []
        tags = [str(t).strip().lower() for t in tags]

        if tag not in tags:
            continue

        candidates.append(
            ResolvedPicto(
                term=term_norm,
                picto_id=picto_id,
                url=str(hit.get("url")),
                score=float(hit.get("score", 0.0)),
                tags=hit.get("tags", []) or [],
                categories=hit.get("categories", []) or [],
                keyword=hit.get("keyword"),
                plural=hit.get("plural"),
            )
        )

    if len(candidates) <= k:
        return candidates

    return random.sample(candidates, k)

def resolve_term_to_picto_strict(term: str, lang: str = "fr", limit: int = 12, expected_type: str | None = None, add_to_cache: bool = True) -> Optional[ResolvedPicto]:
    """
    Strict resolver: only accept if term matches a keyword exactly (case/accents normalized).
    This avoids weird matches (e.g., proper names).
    """
    term_norm = normalize_term(term)
    if not term_norm:
        return None

    client = ArasaacClient(lang=lang)
    results = client.search(term_norm, limit=limit)

    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for cand in results:
        tags, categories = _extract_tags_categories(cand)
        if not _matches_expected_type(expected_type, tags, categories):
            continue
        kws = _extract_keywords(cand)
        if term_norm not in kws:
            continue  # strict: must be exact keyword
        s = _score_candidate(term_norm, cand)
        if best is None or s > best[0]:
            best = (s, cand)

    if best is None:
        return None

    score, cand = best
    picto_id = int(cand.get("_id")) if cand.get("_id") is not None else None
    if picto_id is None:
        return None

    url = client.pictogram_url(picto_id)
    tags, categories = _extract_tags_categories(cand)
    kw, pl = _extract_keyword_info(cand)

    if add_to_cache:

        cache = _load_cache(lang)

        cache[term_norm] = {
            "picto_id": picto_id,
            "url": url,
            "score": score,
            "tags": tags,
            "categories": categories,
            "keyword": kw,
            "plural": pl,
        }

        _save_cache(lang, cache)

    return ResolvedPicto(
        term=term,
        picto_id=picto_id,
        url=url,
        score=score,
        tags=tags,
        categories=categories,
        keyword=kw,
        plural=pl,
    )

def _matches_expected_type(expected_type: str | None, tags: list[str], categories: list[str]) -> bool:
    if not expected_type:
        return True

    exp = expected_type.lower().strip()
    if exp not in EXPECTED_TAGS:
        return True  # type inconnu => pas de filtre

    s = set((t or "").lower() for t in (tags or [])) | set((c or "").lower() for c in (categories or []))
    required = EXPECTED_TAGS[exp]
    return bool(s & required)


def resolve_many_terms_to_picto(terms: List[str], lang: str = "fr", limit: int = 12) -> Dict[str, Optional[ResolvedPicto]]:
    """
    Resolve multiple terms to pictograms.
    Returns a dictionary mapping each term to its resolved pictogram (or None if not found).
    """
    result: Dict[str, Optional[ResolvedPicto]] = {}
    for term in terms:
        result[term] = resolve_term_to_picto(term, lang=lang, limit=limit)
    return result
