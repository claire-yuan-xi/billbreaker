import { gsap, ScrollTrigger, prefersReducedMotion } from "../lib/motion.js";
import { show } from "../lib/dom.js";
import { filterHeadlines, newestFirst, startFeed } from "./feed.js";
import { renderTicker } from "./ticker.js";
import { railMotion } from "./rail-motion.js";
import { listRows, railCards } from "./cards.js";

/** "Today on the floor": live AP headlines as a swipeable rail or a list, plus the top ticker. */
export function initNews(section, ticker) {
  const ui = {
    empty: section.querySelector("[data-news-empty]"),
    railWrap: section.querySelector("[data-news-rail-wrap]"),
    rail: section.querySelector("[data-news-rail]"),
    list: section.querySelector("[data-news-list]"),
    count: section.querySelector("[data-news-count]"),
    refresh: section.querySelector("[data-news-refresh]"),
  };
  const prefs = { sort: "newest", window: "all", view: "rail" };
  let feed = { items: [], loading: true, fetching: false, error: null };
  let dealt = false;
  let drawn = "";
  const motion = railMotion(ui.rail, section.querySelector("[data-news-bar]"));

  const page = (dir) =>
    ui.rail.scrollBy({
      left: dir * ui.rail.clientWidth * 0.85,
      behavior: prefersReducedMotion() ? "auto" : "smooth",
    });

  function render() {
    renderTicker(ticker, newestFirst(feed.items), feed.loading);
    const headlines = filterHeadlines(feed.items, prefs.sort, prefs.window);
    ui.count.textContent =
      headlines.length === feed.items.length
        ? `${feed.items.length} stories`
        : `${headlines.length} of ${feed.items.length} stories`;
    ui.refresh.disabled = feed.fetching;
    ui.refresh.firstElementChild.classList.toggle("animate-spin", feed.fetching);

    const nothing = feed.loading || headlines.length === 0;
    show(ui.empty, nothing);
    show(ui.railWrap, !nothing && prefs.view === "rail");
    show(ui.list, !nothing && prefs.view === "list");
    if (nothing) {
      ui.empty.textContent = feed.loading
        ? "Loading headlines"
        : feed.error
          ? "AP headlines are temporarily unavailable. Try Refresh."
          : "No headlines in this window. Try widening the timeframe.";
      return;
    }
    // Rebuild cards only when the stories or the view change, so polling never resets the rail.
    const signature = prefs.view + headlines.map((h) => h.link).join("|");
    if (signature === drawn) return;
    drawn = signature;
    if (prefs.view === "rail") {
      ui.rail.replaceChildren(...railCards(headlines));
      motion.refresh();
    } else {
      ui.list.replaceChildren(...listRows(headlines));
    }
    dealIn();
    ScrollTrigger.refresh();
  }

  // Cards deal in from the right the first time the section scrolls into view.
  function dealIn() {
    if (dealt || prefersReducedMotion()) return;
    dealt = true;
    gsap.fromTo(
      section.querySelectorAll("[data-news-card]"),
      { x: 120, opacity: 0, rotationY: -28, transformPerspective: 1200, transformOrigin: "0% 50%" },
      {
        x: 0,
        opacity: 1,
        rotationY: 0,
        duration: 1.1,
        ease: "expo.out",
        stagger: { each: 0.07, from: "start" },
        clearProps: "transform",
        scrollTrigger: { trigger: section, start: "top 70%", once: true },
      },
    );
  }

  section.querySelectorAll("[data-toggle]").forEach((group) => {
    group.addEventListener("click", (e) => {
      const button = e.target.closest("[data-value]");
      if (!button) return;
      prefs[group.dataset.toggle] = button.dataset.value;
      group.querySelectorAll("[data-value]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      render();
    });
  });
  section.querySelectorAll("[data-news-page]").forEach((b) => b.addEventListener("click", () => page(Number(b.dataset.newsPage))));
  ui.rail.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") page(1);
    if (e.key === "ArrowLeft") page(-1);
  });

  const { refresh } = startFeed((next) => {
    feed = next;
    render();
  });
  ui.refresh.addEventListener("click", refresh);
}
