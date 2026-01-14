import streamlit as st

from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))


from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms
from qcmgen.pictos.resolve import resolve_term_to_picto_strict, _load_cache


st.set_page_config(page_title="IME QCM Generator", layout="centered")
st.title("IME QCM Generator (v0)")

# padding pour les choix
st.markdown("""
<style>
/* Fond blanc + texte noir */
.stApp { background-color: #ffffff; color: #111827; }

/* Typo plus douce */
html, body, [class*="css"]  {
  font-family: "Nunito", "Trebuchet MS", "Segoe UI", sans-serif;
}

/* Titres */
h1, h2, h3 { color: #111827; }

/* Boutons */
.stButton > button {
  background: #22c55e;
  color: white;
  border-radius: 12px;
  border: none;
  padding: 0.6rem 1rem;
  font-weight: 700;
}
.stButton > button:hover {
  background: #16a34a;
}

/* Zones de saisie */
textarea, input {
  background: #f9fafb !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 10px !important;
}

/* Cartes de choix */
.choice-card {
  background: #f9fafb;
  border: 2px solid #e5e7eb;
  border-radius: 14px;
  padding: 10px;
}
.choice-card.selected {
  border-color: #22c55e;
  background: #ecfdf3;
}

/* Petits badges / labels */
.choice-label {
  font-size: 14px;
  color: #111827;
}
/* Forcer le texte des widgets en noir */
label, .stMarkdown, .stCheckbox, .stRadio, .stToggle, .stSelectbox, .stTextInput, .stTextArea {
  color: #111827 !important;
}

/* Label du toggle (Use LLM) */
div[data-testid="stToggle"] label {
  color: #111827 !important;
}
/* Labels et help text des widgets Streamlit */
div[data-testid="stWidgetLabel"] label,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stCaption"],
div[data-testid="stHelp"] p {
  color: #111827 !important;
  opacity: 1 !important;
}

</style>
""", unsafe_allow_html=True)



if "qcms" not in st.session_state:
    st.session_state.qcms = []

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "picto_cache" not in st.session_state:
    st.session_state.picto_cache = {}

def _picto_url_for(term: str) -> str | None:
    term_norm = term.strip().lower()
    if not term_norm:
        return None

    cache = st.session_state.picto_cache
    if term_norm in cache:
        return cache[term_norm]

    r = resolve_term_to_picto_strict(term_norm, lang="fr")
    url = r.url if r else None
    cache[term_norm] = url
    return url


text = st.text_area('Texte (FR, court)', height = 150, placeholder = "Entrez un texte en français ici...")

use_llm = st.toggle("Utiliser LLM", value=False)

col1, col2 = st.columns([1,1])
with col1:
    generate = st.button("Générer les QCM", type ="primary")
with col2:
    show_debug = st.checkbox("Afficher debug", value = False)

if generate:
    st.session_state.submitted = False

    if not text.strip():
        st.warning("Veuillez entrer un texte avant de générer des QCM.")
    else:

        if use_llm:

            from qcmgen.llm import generate_qcms_from_text_llm

            all_qcms = generate_qcms_from_text_llm(text)

            st.session_state.qcms = all_qcms

        else:
            facts = extract_facts(text)

            all_qcms = []
            for fact in facts:
                all_qcms.extend(generate_qcms(fact))

        st.session_state.qcms = all_qcms

        print(len(st.session_state.qcms), "QCM générés avant filtrage.")

        # load in cache answers that are not in the cache already
        cache_fr = _load_cache('fr')
        for q in st.session_state.qcms:
            answer = q.choices[q.answer_index]
            if answer not in cache_fr:
                print(q.qtype)
                resolve_term_to_picto_strict(answer, expected_type = q.qtype)

        filter = True
        if filter:

            # Filtrer les QCM sans pictos valides
            filtered = []
            for q in st.session_state.qcms:
                urls = [ _picto_url_for(c) for c in q.choices ]
                if all(u is not None for u in urls):
                    filtered.append(q)
                else:
                    print(f'Removing question {q.question} with choices {q.choices}')

            st.session_state.qcms = filtered

            print(len(st.session_state.qcms), "QCM générés après filtrage.")


        # Nettoyer les anciennes réponses
        for k in list(st.session_state.keys()):
            if k.startswith("qcm_"):
             del st.session_state[k]


qcms = st.session_state.qcms

if not qcms:
    st.info("Aucune question générée (texte trop court ou structure non reconnue).")
else:
    st.subheader("QCM générés")
    for i, qcm in enumerate(qcms, start=1):
        st.markdown(f"**QCM {i}:** {qcm.question}")

        key = f"qcm_{i}"
        if key not in st.session_state:
            st.session_state[key] = None

        cols = st.columns(len(qcm.choices))

        for j, (col, choice_text) in enumerate(zip(cols, qcm.choices)):
            with col:
                is_selected = (st.session_state[key] == j)
                card_class = "choice-card selected" if is_selected else "choice-card"

                st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)

                url = _picto_url_for(choice_text)
                if url:
                    st.image(url, width='content')
                else:
                    st.write("❓")

                if show_debug:
                    st.markdown(f"<div class='choice-label'>{choice_text}</div>", unsafe_allow_html=True)

                # Le bouton est la vraie interaction
                if st.button("Sélectionner" if not is_selected else "Sélectionné ✅", key=f"{key}_btn_{j}"):
                    st.session_state[key] = j

                st.markdown("</div>", unsafe_allow_html=True)


                if show_debug:
                    st.caption(choice_text)

        st.divider()  

    submit = st.button("Soumettre les réponses", type="primary")
                       
    if submit and not st.session_state.submitted:
        st.session_state.submitted = True

    if st.session_state.submitted and qcms:
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
