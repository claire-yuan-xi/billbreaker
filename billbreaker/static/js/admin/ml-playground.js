// Model admin playground: ranks pasted bill text for a reader on the server and
// swaps in the rendered tables; Generate runs the model here, then the server
// personalizes its summary and checks the claims.

import { $, $$ } from "../lib/dom.js";
import { postJSON } from "../lib/api.js";
import { readProfile } from "../lib/reader-profile.js";
import { summarize } from "./browser-model.js";

const root = $("[data-playground]");
const example = JSON.parse($("#example-profile").textContent);
const text = $("[data-pg-text]", root);
const generate = $("[data-pg-generate]", root);
const error = $("[data-pg-error]", root);
const progress = $("[data-pg-progress]", root);
let reader = "example";
let timer = 0;

const profile = () => (reader === "example" ? example : readProfile());

async function rank() {
  try {
    const data = await postJSON("/api/admin/ml/rank", { text: text.value, profile: profile() });
    $("[data-pg-terms]", root).innerHTML = data.termsHtml;
    $("[data-pg-table]", root).innerHTML = data.tableHtml;
    generate.disabled = !text.value.trim();
    error.textContent = "";
  } catch (err) {
    error.textContent = err.message;
  }
}

$$("[data-reader]", root).forEach((tab) =>
  tab.addEventListener("click", () => {
    reader = tab.dataset.reader;
    $$("[data-reader]", root).forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
    rank();
  }),
);

text.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(rank, 250);
});

// Shows the model's summary right away, so it stays even if personalizing fails.
function showSummary(general) {
  const block = document.createElement("div");
  block.innerHTML = '<div class="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">General summary</div><p class="mt-2 max-w-3xl text-sm leading-relaxed"></p>';
  $("p", block).textContent = general;
  $("[data-pg-result]", root).replaceChildren(block);
}

const showDownload = (file, share) => {
  progress.textContent = `Downloading model ${file.split("/").pop()} ${Math.round(share * 100)}%`;
};

generate.addEventListener("click", async () => {
  generate.disabled = true;
  error.textContent = "";
  progress.textContent = "Loading model";
  try {
    const general = await summarize(text.value, showDownload);
    showSummary(general);
    progress.textContent = "Personalizing";
    const data = await postJSON("/api/admin/ml/generate", { text: text.value, general, profile: profile() });
    $("[data-pg-result]", root).innerHTML = data.html;
  } catch (err) {
    error.textContent = err.message;
  } finally {
    progress.textContent = "";
    generate.disabled = false;
  }
});
