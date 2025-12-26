import streamlit as st

from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms
from qcmgen.pictos.resolve import resolve_term_to_picto


st.set_page_config(page_title="IME QCM Generator", layout="centered")
st.title("IME QCM Generator (v0)")

# padding pour les choix
st.markdown(
    """
<style>
.choice-card {
  padding: 10px;
  border: 3px solid transparent;
  border-radius: 12px;
  text-align: center;
}
.choice-card.selected {
  border-color: #22c55e; /* vert */
  background: rgba(34, 197, 94, 0.10);
}
.choice-label {
  margin-top: 6px;
  font-size: 14px;
}
</style>
""",
    unsafe_allow_html=True,
)


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

    r = resolve_term_to_picto(term_norm, lang="fr")
    url = r.url if r else None
    cache[term_norm] = url
    return url


text = st.text_area('Texte (FR, court)', height = 150, placeholder = "Entrez un texte en français ici...")

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
        facts = extract_facts(text)

        all_qcms = []
        for fact in facts:
            all_qcms.extend(generate_qcms(fact))

        st.session_state.qcms = all_qcms

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
                    st.image(url, use_container_width=True)
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
