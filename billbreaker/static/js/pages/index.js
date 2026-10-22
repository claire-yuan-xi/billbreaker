import { ScrollTrigger } from "../lib/motion.js";
import { closeModal, setScrollController } from "../lib/modal.js";
import { wirePress } from "../lib/press.js";
import { startSmoothScroll } from "../lib/smooth-scroll.js";
import { $ } from "../lib/dom.js";
import { initCapitolHero } from "../hero/capitol-hero.js";
import { initSiteHeader } from "../landing/site-header.js";
import { initFloatingExplain } from "../landing/floating-explain.js";
import { initBillDrift } from "../landing/bill-drift.js";
import { initRecentBills } from "../landing/recent-bills.js";
import { initNews } from "../news/news-section.js";
import { initSearchDialog } from "../search/search-dialog.js";
import { initSavedSection } from "../saved/saved-section.js";
import { initSavedSheet } from "../saved/saved-sheet.js";

window.BB_STATE_NAMES = JSON.parse($("#state-names").textContent);

setScrollController(startSmoothScroll());
initCapitolHero($("[data-hero]"));
initSiteHeader($("[data-site-header]"), $("#hero"));
initRecentBills($("[data-recent]"));
initNews($("[data-news]"), $("[data-ticker]"));
const saved = initSavedSection($("[data-saved-section]"));
initSavedSheet($("[data-saved-sheet]"), $("[data-open-saved]"), saved.openTools);
initBillDrift($("[data-bill-drift]"), ["#news", "#saved", "[data-bill-avoid]"]);
initFloatingExplain($("[data-floating-explain]"), "#hero");
const openSearch = initSearchDialog($("[data-search-dialog]"), window.BB_STATE_NAMES);
wirePress();

// Every "Search a bill" button on the page opens the same dialog, closing any open panel first.
document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-open-search]");
  if (!button) return;
  const panel = button.closest("dialog[open]");
  if (panel && !panel.matches("[data-search-dialog]")) closeModal(panel);
  openSearch(button.dataset.openSearch);
});

// "Search again" from a bill page that found nothing lands here with the dialog open.
if (new URLSearchParams(window.location.search).has("search")) openSearch("number");

// Lists above the news section change height after load; keep trigger positions honest.
window.addEventListener("load", () => ScrollTrigger.refresh());
