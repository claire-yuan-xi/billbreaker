import { gsap, prefersReducedMotion } from "./motion.js";

/**
 * Tactile feedback for primary buttons: squash on press, elastic rebound on
 * release, an ink ripple from the click point, the arrow (any child with
 * data-press-arrow) kicks forward, and a 10 ms tap on phones that support it.
 * data-press="magnetic" also lets the button lean toward the pointer.
 */
export function attachPress(el, magnetic = false) {
  if (prefersReducedMotion() || el.dataset.pressBound) return;
  el.dataset.pressBound = "1";
  const arrow = el.querySelector("[data-press-arrow]");
  const toX = gsap.quickTo(el, "x", { duration: 0.5, ease: "power3.out" });
  const toY = gsap.quickTo(el, "y", { duration: 0.5, ease: "power3.out" });

  const down = () => {
    gsap.to(el, { scale: 0.95, duration: 0.12, ease: "power2.out", overwrite: "auto" });
    if (arrow) gsap.to(arrow, { scale: 0.85, duration: 0.12, overwrite: "auto" });
  };
  const up = () => {
    gsap.to(el, { scale: 1, duration: 0.7, ease: "elastic.out(1.1, 0.35)", overwrite: "auto" });
    if (arrow) gsap.to(arrow, { scale: 1, duration: 0.7, ease: "elastic.out(1.2, 0.3)" });
  };
  const click = (e) => {
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2.2;
    const ink = document.createElement("span");
    ink.setAttribute("aria-hidden", "true");
    Object.assign(ink.style, {
      position: "absolute",
      left: `${(e.clientX || rect.left + rect.width / 2) - rect.left - size / 2}px`,
      top: `${(e.clientY || rect.top + rect.height / 2) - rect.top - size / 2}px`,
      width: `${size}px`,
      height: `${size}px`,
      borderRadius: "9999px",
      background: "currentColor",
      pointerEvents: "none",
    });
    el.appendChild(ink);
    gsap.fromTo(
      ink,
      { scale: 0, opacity: 0.28 },
      { scale: 1, opacity: 0, duration: 0.75, ease: "power2.out", onComplete: () => ink.remove() },
    );
    if (arrow) gsap.fromTo(arrow, { x: 0 }, { x: 10, duration: 0.18, yoyo: true, repeat: 1 });
    navigator.vibrate?.(10);
  };
  const move = (e) => {
    const r = el.getBoundingClientRect();
    toX((e.clientX - (r.left + r.width / 2)) * 0.18);
    toY((e.clientY - (r.top + r.height / 2)) * 0.25);
  };
  const leave = () => {
    up();
    if (magnetic) gsap.to(el, { x: 0, y: 0, duration: 0.8, ease: "elastic.out(1, 0.4)" });
  };

  el.addEventListener("pointerdown", down);
  el.addEventListener("pointerup", up);
  el.addEventListener("pointerleave", leave);
  el.addEventListener("click", click);
  if (magnetic) el.addEventListener("pointermove", move);
}

/** Wires every [data-press] element under root, including ones added later. */
export function wirePress(root = document) {
  root.querySelectorAll("[data-press]").forEach((el) => attachPress(el, el.dataset.press === "magnetic"));
}
