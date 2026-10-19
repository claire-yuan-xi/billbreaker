import { show } from "../lib/dom.js";
import { closeModal, openModal, wireModal } from "../lib/modal.js";
import { readWatchlist, subscribeWatchlist } from "../lib/watchlist.js";
import { noticeBar } from "./notice.js";
import { renderSavedCards } from "./saved-list.js";

/** The saved list as a side panel, opened from the header button. */
export function initSavedSheet(sheet, openButton, onBackup) {
  wireModal(sheet);
  const notify = noticeBar(sheet.querySelector("[data-notice]"));
  const grid = sheet.querySelector("[data-saved-grid]");

  function render() {
    const items = readWatchlist();
    openButton.setAttribute("aria-label", `Saved bills (${items.length})`);
    show(sheet.querySelector("[data-saved-empty]"), items.length === 0);
    renderSavedCards(grid, items, notify, { compactText: true });
  }

  sheet.querySelector("[data-sheet-backup]").addEventListener("click", () => {
    closeModal(sheet);
    onBackup();
  });
  openButton.addEventListener("click", () => openModal(sheet));
  subscribeWatchlist(render);
  render();
}
