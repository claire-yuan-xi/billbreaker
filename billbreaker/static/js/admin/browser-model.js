// Runs the fine-tuned FLAN-T5 bill explainer in this browser with transformers.js.
// The weights (about 385 MB) download once and stay in the browser cache.

const LIB = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.5";
const MODEL_ID = "clairexi/bill-breaker-t5-onnx";
const PREFIX = "Explain this bill in plain English: ";
const MAX_INPUT = 1024;

let loading = null;

async function load(onProgress) {
  const { AutoTokenizer, AutoModelForSeq2SeqLM, Tensor } = await import(LIB);
  const progress_callback = (event) => {
    if (event.status === "progress" && event.total) onProgress(event.file, event.loaded / event.total);
  };
  const tokenizer = await AutoTokenizer.from_pretrained(MODEL_ID, { progress_callback });
  const model = await AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, {
    dtype: { encoder_model: "fp16", decoder_model_merged: "q8" },
    progress_callback,
  });
  return { tokenizer, model, Tensor };
}

function int64(values) {
  return BigInt64Array.from(values);
}

// pipeline() drops </s> when it truncates, so tokenize by hand and append it.
export async function summarize(billText, onProgress = () => {}) {
  loading ??= load(onProgress).catch((err) => {
    loading = null;
    throw err;
  });
  const { tokenizer, model, Tensor } = await loading;
  const { input_ids } = await tokenizer(PREFIX + billText, { add_special_tokens: false });
  const ids = [...Array.from(input_ids.data).slice(0, MAX_INPUT - 1), BigInt(tokenizer.eos_token_id)];
  const shape = [1, ids.length];
  const out = await model.generate({
    input_ids: new Tensor("int64", int64(ids), shape),
    attention_mask: new Tensor("int64", int64(ids.map(() => 1n)), shape),
    max_new_tokens: 200,
    no_repeat_ngram_size: 3,
  });
  return tokenizer.decode(out[0], { skip_special_tokens: true }).trim();
}
