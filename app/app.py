import streamlit as st

from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms

st.set_page_config(page_title="IME QCM Generator", layout="centered")
st.title("IME QCM Generator (v0)")

text = st.text_area('Texte (FR, court)', height = 150, placeholder = "Entrez un texte en français ici...")

col1, col2 = st.columns([1,1])
with col1:
    generate = st.button("Générer les QCM", type ="primary")
with col2:
    show_debug = st.checkbox("Afficher debug", value = False)

if generate:
    if not text.strip():
        st.warning("Veuillez entrer un texte avant de générer des QCM.")
    else:
        facts = extract_facts(text)
        all_qcms = []
        for fact in facts:
            all_qcms.extend(generate_qcms(fact=fact))

        if not all_qcms:
            st.info("Aucune question générée (texte trop court ou structure non reconnue).")
        else:
            st.subheader("QCM générés")
            for i, qcm in enumerate(all_qcms, start=1):
                st.markdown(f"**QCM {i}:** {qcm.question}")
                st.radio(
                    label = "Choisis une réponse",
                    options = list(range(len(qcm.choices))),
                    format_func=lambda idx, choices=qcm.choices: choices[idx],
                    key=f"qcm_{i}",
                    horizontal=True
                )

                if show_debug:
                    st.caption(f"type={q.qtype} | answer={q.choices[q.answer_index]} | rationale={q.rationale}")

                st.divider()    