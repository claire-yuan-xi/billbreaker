import { cloneTemplate, setText, slot } from "../lib/dom.js";
import { articleHref, cleanTitle, timeAgo, topicFor } from "../lib/format.js";

function fill(node, it) {
  slot(node, "link").href = articleHref(it.link);
  setText(node, "time", timeAgo(it.pubDate));
  setText(node, "topic", topicFor(it.title));
  setText(node, "title", cleanTitle(it.title));
  return node;
}

/** Rail cards: the newest story as a large dark lead card, then numbered cards. */
export function railCards(headlines) {
  return headlines.map((it, i) => {
    const node = fill(cloneTemplate(i === 0 ? "tpl-news-lead" : "tpl-news-card"), it);
    if (i > 0) setText(node, "index", String(i + 1).padStart(2, "0"));
    return node;
  });
}

export function listRows(headlines) {
  return headlines.map((it) => fill(cloneTemplate("tpl-news-row"), it));
}
