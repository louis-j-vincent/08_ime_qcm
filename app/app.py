import streamlit as st

from pathlib import Path
import sys

# for pdfs
import tempfile
import requests
from io import BytesIO
from PIL import Image
from fpdf import FPDF


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from picto_helpers import get_picto_with_variants # robust functions to extract pictos

from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms
from qcmgen.pictos.resolve import resolve_term_to_picto_strict, _load_cache
from qcmgen.sentence_generation import generate_text

def apply_styles():

    st.markdown("""
<style>

<\style>
""", unsafe_allow_html = True)

def render_controls():

    st.set_page_config(page_title="IME QCM Generator", layout="centered")
    st.title("IME QCM Generator (v0)")

    # instantiate text regions and buttons

    text = st.text_area(
        'Texte (FR, court)', 
        height = 150, 
        placeholder = "Entrez un texte en français ici...",
        key = "input_text")

    col1, col2 = st.columns([1,1])
    with col1:
        generate = st.button("Générer les QCM", type ="primary")
        reset = st.button("Réinitialiser", type = "primary")
    with col2:
        use_llm_generation = st.toggle("Utiliser l'assistant IA pour générer le QCM", value=True)
        llm_text_generation = st.toggle("Utiliser l'assistant IA pour générer des phrases", value=False)
        debug_mode = st.checkbox("Afficher debug", value = False)

    return text, use_llm_generation, llm_text_generation, generate, debug_mode, reset

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

    if "llm_text_generation" not in st.session_state:
        st.session_state.llm_text_generation = False

    if "should_generate_text" not in st.session_state:
        st.session_state.should_generate_text = False

    if "input_text" not in st.session_state:
        st.session_state.input_text = ""

def generate_qcms_from_text(text: str = "", 
                            use_llm_generation: bool = False, 
                            require_pictos: bool = True,
                            items: dict = {}):
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

            qcms = generate_qcms_from_text_llm(text, items)
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

    st.markdown(f"*{qcm.paragraph}*")

    st.markdown(f"**QCM {i}:** {qcm.question}")

    keep_key = f"keep_qcm_{i}"
    edit_key = f"edit_qcm_{i}"

    if keep_key not in st.session_state:
        st.session_state[keep_key] = True

    if edit_key not in st.session_state:
        st.session_state[edit_key] = qcm.question

    st.checkbox("Garder cette question", key=keep_key)
    st.text_input("Reformuler la question", key=edit_key)


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
                st.rerun() #actualisation directe pour voir ce qui a été selectionné

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

def _download_picto_to_file(url: str) -> str | None:
    if not url:
        return None
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None

    img = Image.open(BytesIO(r.content)).convert("RGB")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    img.save(tmp.name, "JPEG")
    return tmp.name


def build_pdf(qcms, picto_urls, edited_questions) -> bytes:
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=13)

    for i, q in enumerate(qcms, start=1):
        paragraph = q.paragraph or ""
        question = edited_questions.get(f"edit_qcm_{i}", q.question)

        if paragraph:
            pdf.set_font("Helvetica", style="", size=11)
            pdf.multi_cell(0, 6, f"Contexte: {paragraph}")
            pdf.ln(1)

        pdf.set_font("Helvetica", style="B", size=13)
        pdf.multi_cell(0, 8, f"{i}. {question}")
        pdf.ln(2)

        pdf.set_font("Helvetica", size=11)
        # Affichage des choix sur une seule ligne (4 pictos)
        urls = picto_urls.get(i, [])
        img_size = 18
        cell_width = 45  # largeur par picto + texte

        start_x = pdf.get_x()
        y = pdf.get_y()

        for j, choice in enumerate(q.choices):
            x = start_x + j * cell_width
            pdf.set_xy(x, y)

            url = urls[j] if j < len(urls) else None
            img_path = _download_picto_to_file(url)

            if img_path:
                pdf.image(img_path, x=x, y=y, w=img_size, h=img_size)
                pdf.set_xy(x + img_size + 2, y + 5)
                #pdf.cell(cell_width - img_size - 2, 6, choice)
            #else:
                #pdf.cell(cell_width, 6, choice)

        # sauter une ligne après la rangée
        pdf.ln(img_size + 6)

    return pdf.output(dest="S").encode("latin1")

def collect_selected_questions(qcms) -> list[str]:
    selected = []
    for i, q in enumerate(qcms, start=1):
        if st.session_state.get(f"keep_qcm_{i}", False):
            selected.append(st.session_state.get(f"edit_qcm_{i}", q.question))
    return selected


# instantiate styling
apply_styles()

# instantiate session state()
init_session_state()
if st.session_state.should_generate_text:
    paragraphs, items = generate_text(st.session_state.nb_phrases, st.session_state.complexity)
    st.session_state.input_text = "\n \n".join(paragraphs)
    st.session_state.should_generate_text = False

# instantiate buttons
text, use_llm_generation, llm_text_generation, generate, debug_mode, reset = render_controls()

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

if llm_text_generation:
    # afficher options sur le nombre de phrases à générer et leur complexité
    nb_phrases = st.slider("Nombre de phrases", min_value=1, max_value=10, value=3)
    complexity = st.slider("Complexité", min_value=1, max_value=5, value=3)
    st.session_state.nb_phrases, st.session_state.complexity = nb_phrases, complexity
    generate_text_with_llm = st.button("Générer le texte", type = "primary")

    if generate_text_with_llm:
        st.session_state.should_generate_text = True
        st.rerun()
        

if generate:
    st.subheader("Generation du QCM en cours ... ")
    st.session_state.has_generated = True
    if generate_text_with_llm:
        qcms = generate_qcms_from_text(text = text, 
                                       use_llm_generation = use_llm_generation, 
                                       items = items)
    else:
        qcms = generate_qcms_from_text(text = text, 
                                            use_llm_generation = use_llm_generation) 
    st.session_state.qcms = qcms

if not qcms:
    if not st.session_state.has_generated:
        st.info("Entrez un texte pour commencer.")
    else:
        st.info("Aucune question générée (texte trop court ou structure non reconnue).")
    
else:
    st.subheader("QCM générés")
    render_qcms(qcms)

selected_questions = collect_selected_questions(qcms)

if st.button("Préparer le PDF"):
    selected_qcms = [q for i, q in enumerate(qcms, start=1) if st.session_state.get(f"keep_qcm_{i}", False)]
    edited_questions = {k: v for k, v in st.session_state.items() if k.startswith("edit_qcm_")}

    st.session_state.pdf_bytes = build_pdf(selected_qcms, st.session_state.picto_urls, edited_questions)

if st.session_state.get("pdf_bytes"):
    st.download_button(
        "Télécharger le PDF",
        data=st.session_state.pdf_bytes,
        file_name="qcm_selection.pdf",
        mime="application/pdf"
    )



