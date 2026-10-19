import { show } from "../lib/dom.js";
import { wirePress } from "../lib/press.js";
import { fromRemoteItems, getDeviceId, mergeWatchlist, readWatchlist, subscribeWatchlist } from "../lib/watchlist.js";
import { initBackupTools } from "./backup.js";
import { cloudEnabled, pullCloud } from "./cloud.js";
import { noticeBar } from "./notice.js";
import { renderSavedCards } from "./saved-list.js";

const PREVIEW = 6;

/** The saved-bills block on the home page. */
export function initSavedSection(section) {
  const notify = noticeBar(section.querySelector("[data-notice]"));
  const grid = section.querySelector("[data-saved-grid]");
  const more = section.querySelector("[data-saved-more]");
  const tools = section.querySelector("[data-saved-tools]");
  const toggle = section.querySelector("[data-saved-tools-toggle]");
  const backup = initBackupTools(tools, (text) => notify({ text }));
  let showAll = false;

  function render() {
    const items = readWatchlist();
    document.querySelectorAll("[data-saved-count]").forEach((el) => (el.textContent = String(items.length)));
    show(section.querySelector("[data-saved-empty]"), items.length === 0);
    show(section.querySelector("[data-saved-add]"), items.length > 0);
    renderSavedCards(grid, showAll ? items : items.slice(0, PREVIEW), notify);
    show(more, items.length > PREVIEW);
    more.textContent = showAll ? "Show fewer" : `Show all ${items.length}`;
    backup.render(items);
  }

  more.addEventListener("click", () => {
    showAll = !showAll;
    render();
  });
  toggle.addEventListener("click", () => {
    const open = tools.classList.contains("hidden");
    show(tools, open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Hide backup options" : "Back up & restore";
  });
  subscribeWatchlist(render);
  render();
  wirePress(section);
  pullOnce(notify);
  return { openTools: () => tools.classList.contains("hidden") && toggle.click() };
}

/** Pulls the cloud copy once per visit and merges it in. Does nothing without a backend. */
async function pullOnce(notify) {
  if (!(await cloudEnabled())) return;
  const id = getDeviceId();
  if (!id) return;
  try {
    const r = await pullCloud(id);
    const result = mergeWatchlist(fromRemoteItems(r.items));
    if (result.added || result.merged) {
      notify({ text: `Synced ${result.added} new from the cloud, ${result.merged} updated.` });
    }
  } catch {
    // reconciled on the next visit
  }
}
