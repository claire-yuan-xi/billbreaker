"""Train the Bill Breaker summarizer on this machine instead of Colab.

Same recipe as notebooks/bill_breaker.ipynb (sections 2 to 6): FLAN-T5-base
fine-tuned on 2,000 BillSum bills, with the 100 bills in billsum_100_bills.zip
held out for testing. Runs on Apple Silicon (MPS), CUDA or CPU.

    uv run --python 3.12 --with-requirements ml/requirements-train.txt \
        python ml/train.py --bills ~/Downloads/billsum_100_bills.zip --out ml/bill_breaker_model

A checkpoint is kept every 20 steps in ml/.work; rerunning the same command resumes from it.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
)

SEED = 42
BASE_MODEL = "google/flan-t5-base"
PROMPT = "Explain this bill in plain English: "
MAX_SOURCE, MAX_TARGET = 1024, 256
SHORT_TITLE = re.compile(r"may be cited as the ``(.+?)''", re.S)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def read_bills(zip_path: Path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".txt") or name.startswith("__MACOSX") or "/._" in name:
                continue
            text = z.read(name).decode("utf-8", errors="replace")
            m = SHORT_TITLE.search(text)
            bill_id = Path(name).stem
            rows.append({"bill_id": bill_id, "title": " ".join(m.group(1).split()) if m else bill_id, "text": text})
    return rows


class FreeMpsCache(TrainerCallback):
    """PyTorch's MPS allocator keeps freed blocks; release them each step or a 16 GB Mac runs out."""

    def on_step_end(self, args, state, control, **kwargs):
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()


def device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bills", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("ml/bill_breaker_model"))
    ap.add_argument("--work", type=Path, default=Path("ml/.work"))
    ap.add_argument("--n-train", type=int, default=2000)
    ap.add_argument("--epochs", type=float, default=2)
    # Batch 1 x 16 and Adafactor keep a 16 GB Mac out of swap; same effective batch as the notebook.
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--optim", default="adafactor")
    # Tokens of bill text seen in training; 512 fits a 16 GB Mac, 1024 matches the Colab notebook.
    ap.add_argument("--max-source", type=int, default=MAX_SOURCE)
    ap.add_argument("--drive", type=Path, help="Folder to copy the finished model into (e.g. Google Drive)")
    args = ap.parse_args()

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    print("Device:", device(), flush=True)

    mine = {norm(b["text"]) for b in read_bills(args.bills)}
    print(f"Held out {len(mine)} of your bills", flush=True)

    billsum = load_dataset("FiscalNote/billsum", split="train")
    pool = billsum.filter(lambda r: norm(r["text"]) not in mine)
    pool = pool.shuffle(seed=SEED).select(range(min(args.n_train, len(pool))))
    splits = pool.train_test_split(test_size=0.1, seed=SEED)
    print("Training bills:", len(splits["train"]), "| validation bills:", len(splits["test"]), flush=True)

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL)

    # Fixed-length padding: on MPS every new tensor shape builds and keeps another
    # compute graph, so variable-length batches grow memory until the run dies.
    def preprocess(batch):
        enc = tok([PROMPT + t for t in batch["text"]], max_length=args.max_source,
                  truncation=True, padding="max_length")
        labels = tok(text_target=batch["summary"], max_length=MAX_TARGET,
                     truncation=True, padding="max_length")["input_ids"]
        enc["labels"] = [[t if t != tok.pad_token_id else -100 for t in row] for row in labels]
        return enc

    cols = splits["train"].column_names
    train_tok = splits["train"].map(preprocess, batched=True, remove_columns=cols)
    val_tok = splits["test"].map(preprocess, batched=True, remove_columns=cols)

    trainer = Seq2SeqTrainer(
        model=model,
        args=Seq2SeqTrainingArguments(
            output_dir=str(args.work),
            per_device_train_batch_size=args.batch,
            per_device_eval_batch_size=args.batch,
            gradient_accumulation_steps=16 // args.batch,
            optim=args.optim,
            learning_rate=3e-4,
            num_train_epochs=args.epochs,
            eval_strategy="epoch",
            save_strategy="steps",
            save_steps=20,
            save_total_limit=1,
            gradient_checkpointing=True,
            logging_steps=5,
            report_to="none",
            seed=SEED,
        ),
        train_dataset=train_tok,
        eval_dataset=val_tok,
        data_collator=DataCollatorForSeq2Seq(tok, model=model),
        callbacks=[FreeMpsCache()],
    )
    resume = any(args.work.glob("checkpoint-*"))
    if resume:
        print("Resuming from the last checkpoint in", args.work, flush=True)
    result = trainer.train(resume_from_checkpoint=resume or None)
    metrics = {**result.metrics, **trainer.evaluate()}

    model = trainer.model.eval()
    model.config.use_cache = True
    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    (args.out / "training_metrics.json").write_text(json.dumps(metrics, indent=2))
    shutil.rmtree(args.work, ignore_errors=True)
    print("Saved to", args.out, flush=True)

    if args.drive:
        dest = args.drive / args.out.name
        shutil.copytree(args.out, dest, dirs_exist_ok=True)
        print("Copied to", dest, flush=True)


if __name__ == "__main__":
    main()
