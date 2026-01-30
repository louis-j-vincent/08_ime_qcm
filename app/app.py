import streamlit as st

from pathlib import Path
import sys
import os

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

import numpy as np
import random

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



def render_controls(pdf_uploaded : bool = False):

    st.set_page_config(page_title="IME QCM Generator", layout="centered")
    st.title("IME QCM Generator (v0)")

    text = ""
    reset = False
    llm_text_generation = False

    if not pdf_uploaded:
        # instantiate text regions and buttons

        text = st.text_area(
            'Texte (FR, court)', 
            height = 150, 
            placeholder = "Entrez un texte en français ici...",
            key = "input_text")

    col1, col2 = st.columns([1,1])
    with col1:
        generate = st.button("Générer les QCM", type ="primary")
        if not pdf_uploaded:
            reset = st.button("Réinitialiser", type = "primary")
    with col2:
        use_llm_generation = st.toggle("Utiliser l'assistant IA pour générer le QCM", value=True)
        if not pdf_uploaded:
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
                            paragraphs: str | None = None,
                            use_llm_generation: bool = False, 
                            require_pictos: bool = True,
                            items: dict = {}):
    """
    Given some text, generate qcm questions and answers
    """

    st.session_state.submitted = False

    if not (text.strip() or paragraphs):
        st.warning("Veuillez entrer un texte avant de générer des QCM.")
        return []
    
    else:

        if use_llm_generation:

            from qcmgen.llm import generate_qcms_from_text_llm

            if paragraphs is not None:
                qcms = generate_qcms_from_text_llm(paragraphs = paragraphs, items = items)
            else:
                qcms = generate_qcms_from_text_llm(text = text, items = items)
            st.session_state.qcms = qcms

        else:

            facts = extract_facts(text)
            qcms = []
            for fact in facts:
                qcms.extend(generate_qcms(fact))

        print(len(qcms), "QCM générés avant filtrage.")

        # load in cache answers that are not in the cache already
        cache_fr = _load_cache('fr')

        filtered = []
        counter = 0

        for q in qcms:
            answer = q.choices[q.answer_index]

            # toujours résoudre l'answer (cache gère le hit)
            q.resolved_answer = resolve_term_to_picto_strict(answer, expected_type=q.qtype)
            if q.resolved_answer is None:
                print(f"Couldn't resolve picto for answer {answer}")
                continue

            expected_type = q.qtype if isinstance(q.qtype, str) else None

            distractor_urls = [q.resolved_answer.url]
            choices = [q.resolved_answer.term]
            distractor_idx, nb_distractors = 0, len(q.distractors)
            k = 4

            while len(distractor_urls) < k and distractor_idx < nb_distractors:
                term = q.distractors[distractor_idx]
                distractor_idx += 1
                url = get_picto_with_variants(term, expected_type=expected_type)[1]
                if url is not None:
                    distractor_urls.append(url)
                    choices.append(term)

            if len(distractor_urls) == k:
                order = list(range(len(choices)))
                random.shuffle(order)
                choices = [choices[i] for i in order]
                distractor_urls = [distractor_urls[i] for i in order]

                q.choices = choices

                counter += 1
                filtered.append(q)
                st.session_state.picto_urls[counter] = distractor_urls
            else:
                print(f"Removing question {q.question} with choices {q.choices}")
                print(f"urls found: {[u is not None for u in distractor_urls]}")


        qcms = filtered

        print(len(qcms), "QCM générés après filtrage.")

        # Nettoyer les anciennes réponses
        for k in list(st.session_state.keys()):
            if k.startswith("qcm_"):
             del st.session_state[k]

    return qcms

def display_qcm_question(i, qcm, debug_mode = False, rect = None, page = None):
    """
    Given one qcm element, display it on the streamlit app
    """

    keep_key = f"keep_qcm_{i}"
    edit_key = f"edit_qcm_{i}"

    if keep_key not in st.session_state:
        st.session_state[keep_key] = True

    if edit_key not in st.session_state or st.session_state[edit_key] != qcm.question:
        st.session_state[edit_key] = qcm.question

    col_check, col_img = st.columns([1, 6])

    with col_check:
        st.checkbox("Garder", key=keep_key)

    with col_img:
        # depending on if we have image or not
        if page is not None:
            pix = page.get_pixmap(clip=rect, dpi=200)
            st.image(pix.tobytes("png"))

        else:
            st.markdown(f"<div class='dyslexic'>{qcm.paragraph}</div>", unsafe_allow_html=True)

        #st.markdown(f"<div class='dyslexic'> Question {i}: {qcm.question}</div>", unsafe_allow_html=True)
        st.text_input(f"**Question {i}**", key=edit_key)

    print(qcm.question)
    print(qcm.choices)

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

def render_qcms(qcms, doc = None, selected_sources = None):

    for i, qcm in enumerate(qcms, start=1):
        rect = None
        page = None
        if (
            selected_sources
            and qcm.paragraph_idx is not None
            and qcm.paragraph_idx < len(selected_sources)
            and doc is not None
        ):
            idx_page, idx_doc_pages, rect = selected_sources[qcm.paragraph_idx]
            page = doc[idx_page]
        display_qcm_question(i, qcm, debug_mode, rect=rect, page=page)
        
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

def build_pdf(
    qcms,
    picto_urls,
    edited_questions,
    selected_sources=None,
    doc=None,
    show_paragraph_each_time: bool = False,
) -> bytes:
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_font("OpenDyslexic", "", "data/open_dyslexic/OpenDyslexic3-Regular.ttf", uni=True)
    pdf.add_font("OpenDyslexic", "B", "data/open_dyslexic/OpenDyslexic3-Bold.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    img_size = 40
    cell_width = 50
    bottom_margin = 15

    groups = {}
    group_order = []
    for q in qcms:
        para_key = q.paragraph_idx if q.paragraph_idx is not None else q.paragraph
        if para_key not in groups:
            groups[para_key] = []
            group_order.append(para_key)
        groups[para_key].append(q)

    global_index = 1
    for para_key in group_order:
        group_qcms = groups[para_key]
        paragraph = group_qcms[0].paragraph or ""

        estimated = img_size + 40 + (len(group_qcms) * (img_size + 14))
        if pdf.get_y() + estimated > pdf.h - bottom_margin:
            pdf.add_page()

        context_shown = False
        for q in group_qcms:
            question = edited_questions.get(f"edit_qcm_{global_index}", q.question)

            if show_paragraph_each_time or not context_shown:
                if (
                    selected_sources
                    and doc is not None
                    and q.paragraph_idx is not None
                    and q.paragraph_idx < len(selected_sources)
                ):
                    idx_page, idx_doc_pages, rect = selected_sources[q.paragraph_idx]
                    page = doc[idx_page]
                    pix = page.get_pixmap(clip=rect, dpi=200)

                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    pix.save(tmp.name)

                    img_w = 160
                    img_h = img_w * (pix.height / pix.width)
                    pdf.image(tmp.name, x=pdf.l_margin, y=pdf.get_y(), w=img_w)
                    pdf.ln(img_h + 8)

                    tmp.close()
                    os.unlink(tmp.name)
                elif paragraph:
                    pdf.set_font("OpenDyslexic", size=11)
                    pdf.multi_cell(0, 6, f"Contexte: {paragraph}")
                    pdf.ln(2)

                context_shown = True

            pdf.set_font("OpenDyslexic", style="B", size=13)
            pdf.multi_cell(0, 8, f"{global_index}. {question}")
            pdf.ln(6)

            pdf.set_font("OpenDyslexic", size=11)
            urls = picto_urls.get(global_index, [])

            start_x = pdf.l_margin
            y = pdf.get_y()

            pdf.set_draw_color(0, 0, 0)
            pdf.set_fill_color(255, 255, 255)

            for j, choice in enumerate(q.choices):
                x = start_x + j * cell_width
                pdf.rect(x, y, img_size, img_size, style="DF")

                url = urls[j] if j < len(urls) else None
                img_path = _download_picto_to_file(url)
                if img_path:
                    pdf.image(img_path, x=x, y=y, w=img_size, h=img_size)

            pdf.ln(img_size + 8)
            global_index += 1

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

            parts = re.split(r'[.!?]\s+', text)
            for p in parts:
                p = p.strip()
                if p:
                    if keep:
                        if is_valid_sentence(p):
                            sentences.append(p)

    return sentences

def extract_paragraph_bboxes(page, num_page: int = 0):
    data = page.get_text("dict")
    paragraphs = []
    current_text = ""
    current_rect = None
    keep = False

    gap_threshold = 8  # ajuste si besoin (plus grand = paragraphes plus longs)

    for i, block in enumerate(data["blocks"]):
        if block["type"] != 0:
            continue

        prev_y1 = None

        for j, line in enumerate(block["lines"]):
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if not line_text:
                continue

            if "Lis les phrases" in line_text:
                keep = True
                continue
            if not keep:
                continue
            if not is_valid_sentence(line_text):
                continue

            y0, y1 = line["bbox"][1], line["bbox"][3]

            # Si gros saut vertical -> on ferme le paragraphe courant
            if prev_y1 is not None and (y0 - prev_y1) > gap_threshold and current_text:
                paragraphs.append((current_text.strip(), current_rect))
                current_text = ""
                current_rect = None

            # Ajouter la ligne au paragraphe courant
            current_text += (" " if current_text else "") + line_text
            line_rect = fitz.Rect(line["bbox"])
            current_rect = line_rect if current_rect is None else current_rect | line_rect

            prev_y1 = y1

        # fin de bloc: on ferme le paragraphe si ouvert
        if current_text:
            paragraphs.append((current_text.strip(), current_rect))
            current_text = ""
            current_rect = None

    return paragraphs

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

import re

def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:max_len]

def parse_pdf(pdf_file):

    pdf_bytes = pdf_file.read()
    #sentences = extract_sentences_from_pdf_bytes(pdf_bytes)
    #sentences = extract_sentence_bboxes(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    doc_pages = {}

    sentences = []
    for i,page in enumerate(doc):

        sentences_and_bboxes = extract_paragraph_bboxes(page, num_page = i)
        if len(sentences_and_bboxes) > 0:

            sentences.extend([s[0] for s in sentences_and_bboxes])
            doc_pages[i] = sentences_and_bboxes  # each elt of sentences_and_bboxes is (sentence,bbox)

    return doc, doc_pages

def render_text_from_pdf(doc, doc_pages):
    """
    Outputs checkboxes for all pages where text has been detected
    """

    st.markdown("### Pages disponibles")
    selected_pages = []

    for page_idx in doc_pages.keys():
        if st.checkbox(f'Page {page_idx + 1}', key = f'page_{page_idx}'):
            selected_pages.append(page_idx)

            page = doc[page_idx] # PyMuPDF page object
            for idx, (sentence, bbox) in enumerate(doc_pages[page_idx]):

                col_check, col_img = st.columns([1,6]) # 2 columns, one for checkbox one for image
                
                # générer l’image
                rect = fitz.Rect(bbox)
                pix = page.get_pixmap(clip=rect, dpi=200)
                img_bytes = pix.tobytes("png")

                # checkbox + image
                with col_img:
                    st.image(img_bytes)
                with col_check:
                    keep_key = f"keep_p{page_idx}_s{idx}"
                    st.checkbox("Garder", key=keep_key, value = True)


    selected_sentences = []
    selected_sources = []  # [(page_idx, phrase_idx, rect), ...]

    for page_idx in selected_pages:
        for idx, (sentence, rect) in enumerate(doc_pages[page_idx]):
            if st.session_state.get(f"keep_p{page_idx}_s{idx}"):
                selected_sentences.append(sentence)
                selected_sources.append((page_idx, idx, rect))

    return selected_sentences, selected_sources

# instantiate styling
apply_styles()

# instantiate session state()
init_session_state()
if st.session_state.should_generate_text:
    paragraphs, items = generate_text(st.session_state.nb_phrases, st.session_state.complexity)
    st.session_state.input_text = "\n \n".join(paragraphs)
    st.session_state.should_generate_text = False

st.subheader("Importer un PDF")
pdf_file = st.file_uploader("Uploader un PDF", type=["pdf"])
pdf_uploaded = pdf_file is not None

if pdf_uploaded:

    doc, doc_pages = parse_pdf(pdf_file)
    selected_sentences, selected_sources = render_text_from_pdf(doc, doc_pages)
    st.session_state.selected_sources = selected_sources
    st.session_state.selected_sentences = selected_sentences

else:

    st.session_state.selected_sources = []
    st.session_state.selected_sentences = []
    doc = None

# instantiate buttons
text, use_llm_generation, llm_text_generation, generate, debug_mode, reset = render_controls(pdf_uploaded)

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
    if pdf_file is not None:
        print("Generating from pdf")
        qcms = generate_qcms_from_text(paragraphs = st.session_state.selected_sentences,
                                       use_llm_generation= use_llm_generation)

    elif generate_text_with_llm:
        qcms = generate_qcms_from_text(text = text, 
                                       use_llm_generation = use_llm_generation, 
                                       items = items)
    else:
        qcms = generate_qcms_from_text(text = text, 
                                       use_llm_generation = use_llm_generation) 
    st.session_state.qcms = qcms


if not qcms:
    if not pdf_uploaded:
        if not st.session_state.has_generated:
            st.info("Entrez un texte pour commencer.")
        else:
            st.info("Aucune question générée (texte trop court ou structure non reconnue).")
else:
    st.subheader("QCM générés")
    if pdf_uploaded:
        render_qcms(qcms, selected_sources=st.session_state.selected_sources, doc=doc)
    else:
        render_qcms(qcms)

selected_questions = collect_selected_questions(qcms)

if st.button("Préparer le PDF"):
    selected_qcms = [q for i, q in enumerate(qcms, start=1) if st.session_state.get(f"keep_qcm_{i}", False)]
    edited_questions = {k: v for k, v in st.session_state.items() if k.startswith("edit_qcm_")}

    st.session_state.pdf_bytes = build_pdf(selected_qcms, 
                                           st.session_state.picto_urls, 
                                           edited_questions, 
                                           selected_sources=st.session_state.selected_sources,
                                           doc = doc)

if st.session_state.get("pdf_bytes"):
    st.download_button(
        "Télécharger le PDF",
        data=st.session_state.pdf_bytes,
        file_name="qcm_selection.pdf",
        mime="application/pdf"
    )
