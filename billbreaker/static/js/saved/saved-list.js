import { cloneTemplate, setText, show, slot } from "../lib/dom.js";
import { billHref, formatRelative } from "../lib/format.js";
import { wirePress } from "../lib/press.js";
import { removeAndSync } from "./cloud.js";

/** Renders saved bills as cards into grid; removing one shows an Undo notice. */
export function renderSavedCards(grid, items, notify, { compactText = false } = {}) {
  const names = window.BB_STATE_NAMES ?? {};
  grid.replaceChildren(
    ...items.map((item) => {
      const card = cloneTemplate("tpl-saved-card");
      const label = `${item.state === "US" ? "" : item.state + " "}${item.bill_no}`;
      setText(card, "place", item.state === "US" ? "Federal" : names[item.state] ?? item.state);
      setText(card, "number", item.bill_no);
      setText(card, "saved", `saved ${formatRelative(new Date(item.ts).toISOString())}`);
      setText(card, "title", item.title || label);
      slot(card, "open").href = billHref(item.state, item.bill_no);
      const remove = slot(card, "remove");
      remove.setAttribute("aria-label", `Remove ${label} from saved bills`);
      remove.addEventListener("click", () => {
        removeAndSync(item);
        notify({ text: compactText ? `Removed ${item.bill_no}.` : `Removed ${item.bill_no} from your saved bills.`, undo: item });
      });
      return card;
    }),
  );
  wirePress(grid);
  show(grid, items.length > 0);
}
