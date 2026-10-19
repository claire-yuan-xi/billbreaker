import { cloneTemplate, slot } from "../lib/dom.js";
import { restoreBill } from "../lib/watchlist.js";

/** A short-lived status line in host; ones with an Undo stay up a little longer. */
export function noticeBar(host) {
  let timer = 0;
  const dismiss = () => host.replaceChildren();
  return function show({ text, undo }) {
    clearTimeout(timer);
    const bar = cloneTemplate("tpl-notice");
    slot(bar, "text").textContent = text;
    const undoButton = slot(bar, "undo");
    if (undo) {
      undoButton.classList.remove("hidden");
      undoButton.addEventListener("click", () => {
        restoreBill(undo);
        dismiss();
      });
    }
    slot(bar, "dismiss").addEventListener("click", dismiss);
    host.replaceChildren(bar);
    timer = setTimeout(dismiss, undo ? 7000 : 4000);
  };
}
