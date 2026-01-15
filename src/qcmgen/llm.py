from random import sample
from dotenv import load_dotenv
from pathlib import Path
import os
import sys
import json
from openai import OpenAI
import random
from qcmgen.qcm import QCM


def generate_qcms_from_text_llm(text: str, items: dict = {}) -> list:

    if items == {}:
        # get api key and setup client
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root) + "/qcmgen")
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API_KEY not found in environment variables")
            
        # Load prompt
        llm_prompt = open(project_root.parent / "scripts" / "llm_prompt.txt").read().strip()

        client = OpenAI(api_key=api_key)

        # call llm
        sentences = [s.strip() for s in text.split('.')]
        resp = client.responses.create(
        model="gpt-4o-mini",
        instructions=llm_prompt,
        input="\n".join(f"- {s}" for s in sentences),
        #response_format={"type": "json"}
        )
        
        # clean response and convert to json
        raw = resp.output_text
        start = raw.find("[")
        end = raw.rfind("]") + 1
        output_json = json.loads(raw[start:end])
    else:
        output_json = items

    # Import categories for distractors
    CATEGORIES = json.loads((project_root.parent / "scripts" / "categories.json").read_text())

    # build QCMs with distractors
    all_qcms = []
    for item in output_json:
        qcms = []
        for question in item.get("questions", []):

            try:

                # generate distractors from category
                distractor_candidates = [elt for elt in CATEGORIES[question["category"]] if elt != question["answer"]]
                distractors = random.sample(distractor_candidates, k=3)

                choices = distractors + [question["answer"]]
                random.shuffle(choices)

                qcms.append(
                    QCM(
                        question=question["question"],
                        choices=choices,
                        answer_index=choices.index(question["answer"]),
                        qtype=question.get("qtype", question["category"]),
                        rationale=question.get("rationale", "")
                    )
                )

            except KeyError:
                print(f'LLM hallucinated a new category: {question["category"]}')

        all_qcms.extend(qcms)

    return all_qcms


