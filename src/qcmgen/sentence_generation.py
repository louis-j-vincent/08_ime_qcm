from dotenv import load_dotenv
from pathlib import Path
import os
import sys
import json
from openai import OpenAI

def generate_text(nb_phrases: int = 1, complexity: int = 2):
    """
    Generate sentences which will be used to extract questions after
    """

    # get api key and setup client
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root) + "/qcmgen")
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API_KEY not found in environment variables")
        

    # Load prompt and call llm
    print(complexity, nb_phrases)
    llm_prompt = open(project_root.parent / "scripts" / "llm_text_generation_prompt.txt").read().strip()
    llm_prompt += '\n' + f' Complexity : {complexity} - num_paragraphs : {nb_phrases}'
    client = OpenAI(api_key=api_key)
    resp = client.responses.create(
        model="gpt-4o-mini",
        instructions=llm_prompt,
        input="Generate the JSON now")
    
    raw = resp.output_text
    data = json.loads(raw)

    paragraphs = data["paragraphs"]
    items = data["items"]

    return paragraphs, items