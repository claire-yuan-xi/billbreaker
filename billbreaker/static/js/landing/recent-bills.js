import { cloneTemplate, setText, show, slot } from "../lib/dom.js";
import { billHref } from "../lib/format.js";
import { clearRecent, readRecent } from "../lib/recent.js";

/** The row of recently looked-up bills. Hidden until there is one. */
export function initRecentBills(section) {
  const list = section.querySelector("[data-recent-list]");
  const render = () => {
    const recent = readRecent();
    list.replaceChildren(
      ...recent.map((r) => {
        const chip = cloneTemplate("tpl-recent");
        slot(chip, "link").href = billHref(r.state, r.number);
        setText(chip, "state", r.state);
        setText(chip, "number", r.number);
        setText(chip, "title", r.title);
        return chip;
      }),
    );
    show(section, recent.length > 0);
  };
  section.querySelector("[data-recent-clear]").addEventListener("click", () => {
    clearRecent();
    render();
  });
  render();
}
