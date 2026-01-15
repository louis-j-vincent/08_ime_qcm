import streamlit as st

from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

#from streamlit_helpers import streamlit_mise_en_page


from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms
from qcmgen.pictos.resolve import resolve_term_to_picto_strict, _load_cache

def apply_styles():

    st.markdown("""
<style>

<\style>
""", unsafe_allow_html = True)

def render_controls():

    st.set_page_config(page_title="IME QCM Generator", layout="centered")
    st.title("IME QCM Generator (v0)")

    # instantiate text regions and buttons

    text = st.text_area('Texte (FR, court)', height = 150, placeholder = "Entrez un texte en français ici...")

    col1, col2 = st.columns([1,1])
    with col1:
        generate = st.button("Générer les QCM", type ="primary")
        reset = st.button("Réinitialiser", type = "primary")
    with col2:
        use_llm_generation = st.toggle("Utiliser LLM", value=False)
        debug_mode = st.checkbox("Afficher debug", value = False)

    return text, use_llm_generation, generate, debug_mode, reset

def init_session_state():
    """
    Initialise state session
    """

    if "qcms" not in st.session_state:
        st.session_state.qcms = []

    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    if "picto_cache" not in st.session_state:
        st.session_state.picto_cache = {}

    if "has_generated" not in st.session_state:
        st.session_state.has_generated = False

    if "picto_urls" not in st.session_state:
        st.session_state.picto_urls = {}

import unicodedata

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

def get_picto_with_variants(term: str):
    """
    Loops on all possible variants, starting with the cleanup regular version, and returns the first match
    """
    for candidate in term_variants(term):
        url = get_picto_url(candidate)
        if url:
            return candidate, url
    return None, None


def get_picto_url(term: str) -> str | None:
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

    r = resolve_term_to_picto_strict(term_norm, lang="fr")
    url = r.url if r else None
    cache[term_norm] = url
    return url

def generate_qcms_from_text(text: str = "", use_llm_generation: bool = False, require_pictos: bool = True):
    """
    Given some text, generate qcm questions and answers
    """

    st.session_state.submitted = False

    if not text.strip():
        st.warning("Veuillez entrer un texte avant de générer des QCM.")
        return []
    
    else:

        if use_llm_generation:

            from qcmgen.llm import generate_qcms_from_text_llm

            qcms = generate_qcms_from_text_llm(text)
            st.session_state.qcms = qcms

        else:

            facts = extract_facts(text)
            qcms = []
            for fact in facts:
                qcms.extend(generate_qcms(fact))

        print(len(qcms), "QCM générés avant filtrage.")

        # load in cache answers that are not in the cache already
        cache_fr = _load_cache('fr')

        for q in qcms:
            answer = q.choices[q.answer_index]

            if answer not in cache_fr:
                resolve_term_to_picto_strict(answer, expected_type = q.qtype)

        if require_pictos:

            # Filtrer les QCM sans pictos valides
            filtered = []
            counter = 0
            for q in qcms:
                urls = [ get_picto_with_variants(c)[1] for c in q.choices ]
                if all(u is not None for u in urls):
                    counter += 1
                    filtered.append(q)
                    st.session_state.picto_urls[counter] = urls
                else:
                    print(f'Removing question {q.question} with choices {q.choices}')
                    print(f'urls found: {[u is not None for u in urls]}')

            qcms = filtered

            print(len(qcms), "QCM générés après filtrage.")

        # Nettoyer les anciennes réponses
        for k in list(st.session_state.keys()):
            if k.startswith("qcm_"):
             del st.session_state[k]

    return qcms

def display_qcm_question(i, qcm, debug_mode = False):
    """
    Given one qcm element, display it on the streamlit app
    """

    st.markdown(f"**QCM {i}:** {qcm.question}")

    key = f"qcm_{i}"
    if key not in st.session_state:
        st.session_state[key] = None

    cols = st.columns(len(qcm.choices))

    urls = st.session_state.picto_urls[i]

    for j, (col, choice_text) in enumerate(zip(cols, qcm.choices)):
        with col:
            is_selected = (st.session_state[key] == j)
            card_class = "choice-card selected" if is_selected else "choice-card"

            st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)

            url = urls[j]
            if url:
                st.image(url, width='content')
            else:
                st.write("❓")

            if debug_mode:
                st.markdown(f"<div class='choice-label'>{choice_text}</div>", unsafe_allow_html=True)

            # Le bouton est la vraie interaction
            if st.button("Sélectionner" if not is_selected else "Sélectionné ✅", key=f"{key}_btn_{j}"):
                st.session_state[key] = j

            st.markdown("</div>", unsafe_allow_html=True)

            if debug_mode:
                st.caption(choice_text)

    st.divider()  

def evaluation_and_scoring(qcms):
    """
    Give scoring of how many right answers
    """
    correct_count = 0

    for i, q in enumerate(qcms, start=1):
        user_idx = st.session_state.get(f"qcm_{i}", None)
        if user_idx == q.answer_index:
            correct_count += 1

    st.success(f"Score : {correct_count} / {len(qcms)}")

    # Correction détaillée (utile pour l’enseignant)
    with st.expander("Voir les corrections"):
        for i, q in enumerate(qcms, start=1):
            user_idx = st.session_state.get(f"qcm_{i}", None)
            user_choice = q.choices[user_idx] if user_idx is not None else "(aucune réponse)"
            good_choice = q.choices[q.answer_index]
            ok = (user_idx == q.answer_index)
            st.write(f"{i}. {'✅' if ok else '❌'} {q.question}")
            st.write(f"   Ta réponse : {user_choice}")
            st.write(f"   Bonne réponse : {good_choice}")

def render_qcms(qcms):

    for i, qcm in enumerate(qcms, start=1):
        display_qcm_question(i, qcm, debug_mode)
        
    # create new submit button to evaluate online
    submit = st.button("Soumettre les réponses", type="primary")
                       
    if submit and not st.session_state.submitted:
        st.session_state.submitted = True

    if st.session_state.submitted and qcms:
        evaluation_and_scoring(qcms)

# instantiate styling
apply_styles()

# instantiate buttons
text, use_llm_generation, generate, debug_mode, reset = render_controls()

# instantiate session state()
init_session_state()
qcms = st.session_state.qcms

if reset:
    st.session_state.qcms = []
    st.session_state.submitted = False
    st.session_state.has_generated = False
    st.session_state.picto_urls = {}
    # delete qcm answer keys
    keys_to_delete = [ key for key in st.session_state.keys() if key.startswith('qcm_')]
    for key in keys_to_delete:
        del st.session_state[key]

if generate:
    st.subheader("Generation du QCM en cours ... ")
    st.session_state.has_generated = True
    qcms = generate_qcms_from_text(text, use_llm_generation)
    st.session_state.qcms = qcms

if not qcms:
    if not st.session_state.has_generated:
        st.info("Entrez un texte pour commencer.")
    else:
        st.info("Aucune question générée (texte trop court ou structure non reconnue).")
    
else:
    st.subheader("QCM générés")
    render_qcms(qcms)


