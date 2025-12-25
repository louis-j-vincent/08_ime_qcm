import streamlit as st

st.set_page_config(page_title="IME QCM Generator", layout="wide")
st.title("IME QCM Generator (v0)")

text = st.text_area("Colle un texte court (<50 mots)", height=120)

if st.button("Générer (placeholder)"):
    if not text.strip():
        st.warning("Colle un texte d'abord.")
    else:
        st.success("OK. Prochaine étape: parsing spaCy + templates QCM.")
        st.write("Texte reçu:")
        st.write(text)
