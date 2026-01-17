import streamlit as st

from pathlib import Path
import sys

# generate pdfs
import tempfile
import requests
from io import BytesIO
from PIL import Image
from fpdf import FPDF

# read pdfs
import re
import fitz  # PyMuPDF
from io import BytesIO

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "app"))

from picto_helpers import get_picto_with_variants # robust functions to extract pictos

from qcmgen.nlp import extract_facts
from qcmgen.qcm import generate_qcms
from qcmgen.pictos.resolve import resolve_term_to_picto_strict, _load_cache
from qcmgen.sentence_generation import generate_text

import base64
from pathlib import Path


def apply_styles():

    st.markdown("""
<style>
.dyslexic { font-family: "opendyslexic", sans-serif; }
</style>
""", unsafe_allow_html=True)



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
                expected_type = q.qtype if isinstance(q.qtype, str) else None
                print(expected_type)
                urls = [ get_picto_with_variants(c, expected_type=expected_type)[1] for c in q.choices ]
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

    #st.markdown(f"*{qcm.paragraph}*")
    st.markdown(f"<div class='dyslexic'>{qcm.paragraph}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='dyslexic'> **QCM {i}:** {qcm.question}</div>", unsafe_allow_html=True)


    #st.markdown(f"**QCM {i}:** {qcm.question}")

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
    pdf.add_font("OpenDyslexic", "", "data/open_dyslexic/OpenDyslexic3-Regular.ttf", uni=True)
    pdf.add_font("OpenDyslexic", "B", "data/open_dyslexic/OpenDyslexic3-Bold.ttf", uni=True)  # si tu as le bold
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    for i, q in enumerate(qcms, start=1):
        paragraph = q.paragraph or ""
        question = edited_questions.get(f"edit_qcm_{i}", q.question)

        if paragraph:
            pdf.set_font("OpenDyslexic", style="", size=11)
            pdf.multi_cell(0, 6, f"Contexte: {paragraph}")
            pdf.ln(1)

        pdf.set_font("OpenDyslexic", style="B", size=13)
        pdf.multi_cell(0, 8, f"{i}. {question}")
        pdf.ln(2)

        pdf.set_font("OpenDyslexic", size=11)
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

def extract_sentences_from_pdf_bytes(pdf_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    sentences = []

    for page in doc:
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0])) # sort by descending order on page

        keep = False

        for i, b in enumerate(blocks):
            bbox = fitz.Rect(b[0], b[1], b[2], b[3])
            text = b[4].strip()
            if not text:
                continue

            if "Lis les phrases" in text:
                keep = True
                continue

            if keep:
                pix = page.get_pixmap(clip=bbox, dpi=200)
                pix.save(f'export/phrase_{i}.png')

            parts = re.split(r'[.!?]\s+', text)
            for p in parts:
                p = p.strip()
                if p:
                    if keep:
                        if is_valid_sentence(p):
                            sentences.append(p)

    return sentences

def extract_sentence_bboxes(page, num_page : int = 0):
    data = page.get_text("dict")
    sentences = []
    current_text = ""
    current_rect = None
    keep = False

    for i, block in enumerate(data["blocks"]):
        if block["type"] != 0:
            continue
        for j, line in enumerate(block["lines"]):
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if not line_text:
                continue

            #print("LINE:", line_text)

            if "Lis les phrases" in line_text:
                print("FOUND trigger")

            # Déclencheur "Lis les phrases"
            if "Lis les phrases" in line_text:
                keep = True
                continue

            if not keep:
                continue

            if is_valid_sentence(line_text):

                # Ajouter cette ligne au buffer
                current_text += (" " if current_text else "") + line_text
                line_rect = fitz.Rect(line["bbox"])
                current_rect = line_rect if current_rect is None else current_rect | line_rect

                # Fin de phrase si la ligne se termine par . ! ?
                if re.search(r"[.!?]\s*$", line_text):
                    #sentences.append((current_text.strip(), current_rect))
                    #current_text = ""
                    #current_rect = None
                    #sentences.append(current_text.strip())
                    sentences.append((current_text.strip(), current_rect))
                    pix = page.get_pixmap(clip=line["bbox"], dpi=200)
                    pix.save(f'export/phrase_{num_page}_{i}_{j}.png')

    return sentences

def is_valid_sentence(sentence : str):
    """
    Given a sentence string, chose if we keep it or not
    """
    forbidden = ['(', ')', '"', '“', '”']
    is_valid = ( len(sentence.split(' ')) > 1 ) # more than 1 word
    is_valid &= ('TitLine' not in sentence) # no TitLine string
    is_valid &= (not any(ch in sentence for ch in forbidden)) # no forbidden character
    is_valid &= (sentence[0].isupper()) # first letter is in Capital
    return  is_valid

def color_to_hex(c: int) -> str:
    r = (c >> 16) & 255
    g = (c >> 8) & 255
    b = c & 255
    return f"#{r:02x}{g:02x}{b:02x}"

def extract_colored_spans(page):
    spans = []
    data = page.get_text("dict")

    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text:
                    spans.append({
                        "text": text,
                        "color": color_to_hex(span["color"])
                    })
    return spans

import re

def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:max_len]

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

st.subheader("Importer un PDF")
pdf_file = st.file_uploader("Uploader un PDF", type=["pdf"])

if pdf_file is not None:
    pdf_bytes = pdf_file.read()
    #sentences = extract_sentences_from_pdf_bytes(pdf_bytes)
    #sentences = extract_sentence_bboxes(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    doc_dict = {}

    sentences = []
    for i,page in enumerate(doc):

        sentences_and_bboxes = extract_sentence_bboxes(page, num_page = i)
        sentences.extend([s[0] for s in sentences_and_bboxes])
        
        doc_dict[f'page_{i}'] = {j: s for j, s in enumerate(sentences_and_bboxes)}  # each elt of sentences_and_bboxes is (sentence,bbox)

    st.markdown("**Lis les phrases**")
    for s in sentences:
        st.markdown(f"<div class='dyslexic'>- {s}</div>", unsafe_allow_html=True)

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

else:
    generate_text_with_llm = False
        

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



