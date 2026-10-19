"""Bill Breaker model server (runs as a free Hugging Face Space).

POST /explain {"text", "title", "profile"} returns
{"general", "personalized", "sections"}: the fine-tuned FLAN-T5 summary, a version
rewritten for the reader by Qwen2.5-1.5B-Instruct, and the sections that drove it.
Reader answers are used for this one request only; nothing is stored or logged.
"""

import os
from functools import lru_cache

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from sections import clean_profile, rank_sections

MODEL_ID = os.environ.get("MODEL_ID", "")
PERSONALIZER = os.environ.get("PERSONALIZER", "Qwen/Qwen2.5-1.5B-Instruct")
PROMPT = "Explain this bill in plain English: "
MAX_SOURCE, MAX_TARGET = 1024, 256
ALLOWED_ORIGINS = [
    "https://billbreaker.org",
    "https://www.billbreaker.org",
    "http://localhost:3000",
]

SYSTEM = (
    "You explain US congressional bills to ordinary people in plain English at about an 8th-grade reading level. "
    "Use only the bill summary and bill sections you are given; never invent facts, numbers, or effects. "
    "A bill is a proposal and may never have become law, so do not say it is law. "
    "Stay neutral: no political opinions and no advice on how to vote. "
    "Write two short parts with these headings: 'What this bill does' (3 to 5 bullet points) and "
    "'What it could mean for you' (2 to 4 sentences tied to the reader's details). "
    "If the bill does not clearly affect this reader, say that plainly instead of stretching."
)

torch.set_num_threads(os.cpu_count() or 2)

app = FastAPI(title="Bill Breaker model")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["content-type"],
)


class ExplainRequest(BaseModel):
    text: str = Field(min_length=80, max_length=200_000)
    title: str = Field(default="This bill", max_length=300)
    profile: dict[str, str] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def summarizer():
    if not MODEL_ID:
        raise RuntimeError("MODEL_ID is not set")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID).eval()
    return tok, model


@lru_cache(maxsize=1)
def writer():
    return pipeline("text-generation", model=PERSONALIZER, torch_dtype=torch.float32, device_map="cpu")


def summarize(text):
    tok, model = summarizer()
    inputs = tok(PROMPT + text, max_length=MAX_SOURCE, truncation=True, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=MAX_TARGET, num_beams=4,
                             no_repeat_ngram_size=3, early_stopping=True)
    return tok.decode(out[0], skip_special_tokens=True)


def personalize(title, general, sections, profile):
    excerpts = "\n\n".join(
        f"SEC. {s['section']} {s['heading']}\n{' '.join(s['body'].split()[:250])}" for s in sections
    ) or "(No sections matched this reader's details.)"
    reader = "\n".join(f"- {k}: {v}" for k, v in profile.items()) or "- (no details given)"
    user = (f"Bill: {title}\n\nGeneral summary:\n{general}\n\n"
            f"Sections most related to the reader:\n{excerpts}\n\nAbout the reader:\n{reader}")
    out = writer()([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                   max_new_tokens=350, do_sample=False)
    return out[0]["generated_text"][-1]["content"]


@app.on_event("startup")
def warm_up():
    summarizer()
    writer()


@app.get("/")
def health():
    return {"ok": True, "model": MODEL_ID, "personalizer": PERSONALIZER}


@app.post("/explain")
def explain(req: ExplainRequest):
    profile = clean_profile(req.profile)
    try:
        general = summarize(req.text)
        sections = rank_sections(req.text, profile)
        personalized = personalize(req.title, general, sections, profile)
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    return {
        "general": general,
        "personalized": personalized,
        "sections": [
            {k: s[k] for k in ("section", "heading", "score", "matched_terms")} for s in sections
        ],
    }
