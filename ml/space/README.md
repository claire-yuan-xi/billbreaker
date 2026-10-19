---
title: Bill Breaker
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

Serves the Bill Breaker model for billbreaker.org. `POST /explain` with
`{"text", "title", "profile"}` returns the fine-tuned FLAN-T5 summary, a version
written for the reader, and the bill sections that drove it.

Set by `notebooks/bill_breaker_deploy.ipynb`: the `MODEL_ID` variable points at the
fine-tuned model on the Hugging Face Hub.
