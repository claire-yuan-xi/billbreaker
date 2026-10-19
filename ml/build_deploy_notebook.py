"""Builds notebooks/bill_breaker_deploy.ipynb from the files in ml/space.

The notebook carries the Space's files inside it, so running it in Colab needs nothing
but a Hugging Face token. Re-run this script after changing anything in ml/space:

    python3 ml/build_deploy_notebook.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACE_DIR = ROOT / "ml" / "space"
OUT = ROOT / "notebooks" / "bill_breaker_deploy.ipynb"
SPACE_FILES = ["app.py", "sections.py", "requirements.txt", "Dockerfile", "README.md"]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


INTRO = """
# Bill Breaker: train the model and put it online

This notebook trains the Bill Breaker model and hosts it for billbreaker.org.

1. Go to **Runtime > Change runtime type**, pick **T4 GPU**, and click **Save**.
2. Go to **Runtime > Run all**.
3. A box near the top asks for a **Hugging Face token**. To get one:
   - Sign in at huggingface.co (or make a free account).
   - Open **huggingface.co/settings/tokens** and click **Create new token**.
   - Choose **Write**, give it any name, then create and copy it.
   - Paste it into the box and press Enter.
4. Leave this tab open. Training takes about an hour on a T4.
5. The last cell prints a link. Set it as `ML_ENDPOINT` in the site's Vercel settings.

The trained model is saved to your Hugging Face account, so nothing is lost if Colab disconnects afterwards. If no GPU is free, the notebook still runs on CPU with a smaller, quicker training set.
"""

SETUP = """
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                       "transformers>=4.44", "datasets>=2.20", "accelerate>=0.33",
                       "sentencepiece", "huggingface_hub>=0.24"])

from getpass import getpass
from huggingface_hub import HfApi, login

HF_TOKEN = None
try:
    from google.colab import userdata
    HF_TOKEN = userdata.get("HF_TOKEN")
except Exception:
    pass
if not HF_TOKEN:
    HF_TOKEN = getpass("Paste your Hugging Face token (Write access) and press Enter: ").strip()

login(token=HF_TOKEN, add_to_git_credential=False)
api = HfApi(token=HF_TOKEN)
USER = api.whoami()["name"]
MODEL_REPO = f"{USER}/bill-breaker-t5"
SPACE_REPO = f"{USER}/billbreaker"
print("Signed in to Hugging Face as", USER)
"""

DATA = """
import random
import numpy as np
import torch
from datasets import load_dataset

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

GPU = torch.cuda.is_available()
N_TRAIN, EPOCHS = (2000, 2) if GPU else (300, 1)
print("GPU:", torch.cuda.get_device_name(0) if GPU else "none, using CPU with a smaller training set")

billsum = load_dataset("FiscalNote/billsum", split="train")
pool = billsum.shuffle(seed=SEED).select(range(N_TRAIN))
splits = pool.train_test_split(test_size=0.1, seed=SEED)
train_ds, val_ds = splits["train"], splits["test"]
print("Training bills:", len(train_ds), "| validation bills:", len(val_ds))
"""

TRAIN = """
from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq,
                          Seq2SeqTrainer, Seq2SeqTrainingArguments)

BASE_MODEL = "google/flan-t5-base"
PROMPT = "Explain this bill in plain English: "
MAX_SOURCE, MAX_TARGET = 1024, 256

tok = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL)


def preprocess(batch):
    enc = tok([PROMPT + t for t in batch["text"]], max_length=MAX_SOURCE, truncation=True)
    enc["labels"] = tok(text_target=batch["summary"], max_length=MAX_TARGET, truncation=True)["input_ids"]
    return enc


cols = train_ds.column_names
train_tok = train_ds.map(preprocess, batched=True, remove_columns=cols)
val_tok = val_ds.map(preprocess, batched=True, remove_columns=cols)

args = Seq2SeqTrainingArguments(
    output_dir="bill-breaker-t5",
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=3e-4,
    num_train_epochs=EPOCHS,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=1,
    load_best_model_at_end=True,
    gradient_checkpointing=True,
    logging_steps=25,
    report_to="none",
    seed=SEED,
)
trainer = Seq2SeqTrainer(
    model=model,
    args=args,
    train_dataset=train_tok,
    eval_dataset=val_tok,
    data_collator=DataCollatorForSeq2Seq(tok, model=model),
)
trainer.train()
model = trainer.model.eval()
model.config.use_cache = True
"""

SAVE = """
model.push_to_hub(MODEL_REPO, commit_message="Bill Breaker fine-tuned FLAN-T5")
tok.push_to_hub(MODEL_REPO, commit_message="Tokenizer")
print("Model saved to https://huggingface.co/" + MODEL_REPO)
"""

SPACE = """
from pathlib import Path

space_dir = Path("billbreaker_space")
space_dir.mkdir(exist_ok=True)
for name, content in SPACE_FILES.items():
    (space_dir / name).write_text(content)

api.create_repo(SPACE_REPO, repo_type="space", space_sdk="docker", exist_ok=True)
api.add_space_variable(SPACE_REPO, "MODEL_ID", MODEL_REPO)
api.upload_folder(repo_id=SPACE_REPO, repo_type="space", folder_path=str(space_dir),
                  commit_message="Bill Breaker model server")
print("Space created: https://huggingface.co/spaces/" + SPACE_REPO)
"""

WAIT = """
import time
import requests

host = "https://" + SPACE_REPO.lower().replace("/", "-").replace("_", "-").replace(".", "-") + ".hf.space"
print("Waiting for the Space to build and load the models (usually 5 to 15 minutes)...")
deadline = time.time() + 40 * 60
while True:
    stage = api.get_space_runtime(SPACE_REPO).stage
    if stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
        raise RuntimeError(f"The Space stopped with {stage}. Open https://huggingface.co/spaces/{SPACE_REPO} and check its Logs tab.")
    if stage == "RUNNING":
        try:
            if requests.get(host + "/", timeout=30).ok:
                break
        except requests.RequestException:
            pass
    if time.time() > deadline:
        raise TimeoutError(f"Still starting after 40 minutes. Check https://huggingface.co/spaces/{SPACE_REPO}")
    time.sleep(20)

sample = {
    "title": "Example bill",
    "text": "SEC. 1. SHORT TITLE. This Act may be cited as the Example Act. "
            "SEC. 2. STUDENT LOANS. The Secretary of Education shall reduce interest on "
            "federal student loans for borrowers enrolled at a college or university.",
    "profile": {"age": "18-24", "work": "college student"},
}
reply = requests.post(host + "/explain", json=sample, timeout=900)
reply.raise_for_status()
print(reply.json()["general"])
print()
print("=" * 60)
print("Done. Set this as ML_ENDPOINT on Vercel:")
print(host + "/explain")
print("=" * 60)
"""


def main():
    files = {name: (SPACE_DIR / name).read_text() for name in SPACE_FILES}
    cells = [
        md(INTRO),
        md("## 1. Sign in to Hugging Face"),
        code(SETUP),
        md("## 2. Training data: BillSum (bill text paired with official summaries)"),
        code(DATA),
        md("## 3. Fine-tune FLAN-T5"),
        code(TRAIN),
        md("## 4. Save the model to your Hugging Face account"),
        code(SAVE),
        md("## 5. Put the model online (a free Hugging Face Space)"),
        code("SPACE_FILES = " + json.dumps(files, indent=1)),
        code(SPACE),
        md("## 6. Wait for it to start and test it"),
        code(WAIT),
    ]
    nb = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print("Wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
