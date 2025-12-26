import streamlit as st

from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms

st.set_page_config(page_title="IME QCM Generator", layout="centered")
st.title("IME QCM Generator (v0)")

if "qcms" not in st.session_state:
    st.session_state.qcms = []

if "submitted" not in st.session_state:
    st.session_state.submitted = False


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
        st.radio(
            label = "Choisis une réponse",
            options = list(range(len(qcm.choices))),
            format_func=lambda idx, choices=qcm.choices: choices[idx],
            key=f"qcm_{i}",
            horizontal=True
        )

        if show_debug:
            st.caption(f"type={qcm.qtype} | answer={qcm.choices[qcm.answer_index]} | rationale={qcm.rationale}")

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
