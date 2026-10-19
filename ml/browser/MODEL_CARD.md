---
library_name: transformers.js
base_model: clairexi/bill-breaker-t5
pipeline_tag: summarization
---

Browser build of [clairexi/bill-breaker-t5](https://huggingface.co/clairexi/bill-breaker-t5)
(FLAN-T5-base fine-tuned on BillSum) for [transformers.js](https://huggingface.co/docs/transformers.js).

- `onnx/encoder_model_fp16.onnx` (16-bit encoder; int8 changed facts in summaries)
- `onnx/decoder_model_merged_quantized.onnx` (int8 per-channel decoder)

```js
import { AutoTokenizer, AutoModelForSeq2SeqLM, Tensor } from "@huggingface/transformers";

const id = "clairexi/bill-breaker-t5-onnx";
const tok = await AutoTokenizer.from_pretrained(id);
const model = await AutoModelForSeq2SeqLM.from_pretrained(id, {
  dtype: { encoder_model: "fp16", decoder_model_merged: "q8" },
});

// Keep the first 1023 tokens and end with </s>, as the model was trained.
const { input_ids } = await tok("Explain this bill in plain English: " + billText, { add_special_tokens: false });
const ids = [...Array.from(input_ids.data).slice(0, 1023), BigInt(tok.eos_token_id)];
const out = await model.generate({
  input_ids: new Tensor("int64", BigInt64Array.from(ids), [1, ids.length]),
  attention_mask: new Tensor("int64", BigInt64Array.from(ids.map(() => 1n)), [1, ids.length]),
  max_new_tokens: 200,
  no_repeat_ngram_size: 3,
});
const summary = tok.decode(out[0], { skip_special_tokens: true });
```

The tokenizer files set `add_prefix_space` and `model_max_length: 1024` so transformers.js
tokenizes the same way as Python.
