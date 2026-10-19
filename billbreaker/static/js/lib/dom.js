// Tiny helpers for cloning <template> markup and filling its data-slot elements.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Clones the first element of <template id=...>. */
export function cloneTemplate(id) {
  const tpl = document.getElementById(id);
  return tpl.content.firstElementChild.cloneNode(true);
}

/** Returns the element with data-slot=name inside root (or root itself). */
export function slot(root, name) {
  if (root.dataset.slot === name) return root;
  return root.querySelector(`[data-slot="${name}"]`);
}

export function setText(root, name, text) {
  const el = slot(root, name);
  if (el) el.textContent = text;
  return el;
}

export function show(el, on) {
  if (el) el.classList.toggle("hidden", !on);
}
