import { isSaved, readWatchlist, retitleBill, subscribeWatchlist } from "../lib/watchlist.js";
import { removeAndSync, saveAndSync } from "../saved/cloud.js";

/** Save or unsave this bill; once saved, links back to the saved list. */
export function initSaveToggle(wrap, state, billNo, getTitle) {
  const button = wrap.querySelector("[data-save-toggle]");
  const label = wrap.querySelector("[data-save-label]");
  const star = wrap.querySelector("[data-star]");
  const link = wrap.querySelector("[data-saved-link]");

  function render() {
    const list = readWatchlist();
    const saved = isSaved(state, billNo, list);
    button.setAttribute("aria-pressed", String(saved));
    label.textContent = saved ? "Saved" : "Save bill";
    star.setAttribute("fill", saved ? "currentColor" : "none");
    link.classList.toggle("hidden", !saved);
    link.textContent = `See saved bills (${list.length})`;
    // Bills saved before the real title arrived get it filled in later.
    if (saved) retitleBill(state, billNo, getTitle());
  }

  button.addEventListener("click", () => {
    if (isSaved(state, billNo)) removeAndSync({ state, bill_no: billNo });
    else saveAndSync(state, billNo, getTitle());
  });
  wrap.classList.replace("hidden", "inline-flex");
  subscribeWatchlist(render);
  render();
  return { refresh: render };
}
