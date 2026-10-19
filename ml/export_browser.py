"""Build the transformers.js (in-browser) copy of a trained model and upload it.

    uv run --no-project --python 3.12 --with "optimum[exporters]==1.23.3" \
        --with "transformers==4.46.3" --with "torch==2.5.1" --with "onnx==1.17.0" \
        --with "onnxruntime==1.20.1" --with "onnxconverter-common==1.14.0" \
        --with "numpy<2" --with sentencepiece --with huggingface_hub \
        python ml/export_browser.py --model ml/bill_breaker_model

Choices that were checked against the PyTorch model on held-out bills:
- encoder in 16-bit: int8 changed facts (wrong agency, garbled act names)
- decoder in int8 per channel, including its If-branch subgraphs
- tokenizer gets add_prefix_space, or transformers.js splits the first word
  differently from Python, and model_max_length 1024 instead of 512
Callers must still end the input with </s> after truncating (see the repo README).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import onnx
from huggingface_hub import HfApi
from onnxconverter_common import float16
from onnxruntime.quantization import QuantType, quantize_dynamic

TOKENIZER_FILES = [
    "config.json",
    "generation_config.json",
    "special_tokens_map.json",
    "spiece.model",
    "tokenizer.json",
    "tokenizer_config.json",
]


def export_onnx(model_dir: Path, work: Path) -> None:
    subprocess.run(
        ["optimum-cli", "export", "onnx", "--model", str(model_dir),
         "--task", "text2text-generation-with-past", str(work)],
        check=True,
    )


def patch_tokenizer(out: Path) -> None:
    tok = json.loads((out / "tokenizer.json").read_text())
    for part in ("pre_tokenizer", "decoder"):
        if tok.get(part, {}).get("type") == "Metaspace":
            tok[part]["add_prefix_space"] = True
    (out / "tokenizer.json").write_text(json.dumps(tok, ensure_ascii=False))
    cfg = json.loads((out / "tokenizer_config.json").read_text())
    cfg["model_max_length"] = 1024
    (out / "tokenizer_config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def build(work: Path, out: Path) -> None:
    (out / "onnx").mkdir(parents=True, exist_ok=True)
    for name in TOKENIZER_FILES:
        shutil.copy(work / name, out / name)
    patch_tokenizer(out)
    encoder = onnx.load(str(work / "encoder_model.onnx"))
    onnx.save(float16.convert_float_to_float16(encoder, keep_io_types=True),
              str(out / "onnx" / "encoder_model_fp16.onnx"))
    quantize_dynamic(
        str(work / "decoder_model_merged.onnx"),
        str(out / "onnx" / "decoder_model_merged_quantized.onnx"),
        weight_type=QuantType.QInt8,
        per_channel=True,
        extra_options={"EnableSubgraph": True},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="Folder written by ml/train.py")
    ap.add_argument("--work", type=Path, default=Path("ml/.onnx"))
    ap.add_argument("--out", type=Path, default=Path("ml/.onnx_upload"))
    ap.add_argument("--repo-name", default="bill-breaker-t5-onnx")
    ap.add_argument("--readme", type=Path, help="Model card to upload as README.md")
    args = ap.parse_args()

    export_onnx(args.model, args.work)
    build(args.work, args.out)
    if args.readme:
        shutil.copy(args.readme, args.out / "README.md")

    api = HfApi()
    repo = f"{api.whoami()['name']}/{args.repo_name}"
    api.create_repo(repo, exist_ok=True)
    api.upload_folder(repo_id=repo, folder_path=str(args.out),
                      commit_message="Browser (transformers.js) build")
    print("https://huggingface.co/" + repo)


if __name__ == "__main__":
    main()
