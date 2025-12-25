# IME QCM Generator (v0)

Tool to generate simple reading-comprehension multiple-choice questions (QCM)
from short French texts, designed for IME-level students.

The goal is to assist teachers by automatically producing pedagogical material
that remains **simple, controllable, and editable**.

---

## Features (v0)

- Input: short French text (< 50 words)
- NLP-based extraction of:
  - subject
  - main verb
  - object
  - adjective–noun pairs
- Automatic generation of simple QCM:
  - object-based questions (e.g. *Que promène Martin ?*)
  - adjective-based questions (e.g. *Quel animal est gris ?*)
- Editable interface (Streamlit)
- Designed to be extended with pictograms and PDF export in later versions

---

## Tech stack

- **Python**
- **spaCy (French, `fr_core_news_md`)** for classical NLP
- **Streamlit** for the user interface

This project deliberately avoids LLM-based generation in v0 to ensure:
- zero token cost
- deterministic behavior
- pedagogical control

---

## Installation

### 1. Create and activate a virtual environment

On macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

### 2. Install dependencies

pip install -r requirements.txt

### install spaCy French model (required)
⚠️ This project requires the medium French model for reliable parsing.

python -m spacy download fr_core_news_md

### Run the app
streamlit run app/app.py

### Notes (v0)
Uses spaCy dependency parsing + templates (no LLM).

Known limitation: time expressions may be attached to noun phrases.