import { gsap, prefersReducedMotion } from "../lib/motion.js";

/**
 * Motion for the horizontal news rail:
 * the progress hairline follows the scroll position with a little easing,
 * cards lean with the rail's scroll speed and spring back when it stops,
 * and under a mouse a card tilts toward the pointer with a soft glare.
 * Call once; it re-reads the cards each time refresh() is called.
 */
export function railMotion(rail, bar) {
  const reduced = prefersReducedMotion();
  const toBar = gsap.quickTo(bar, "scaleX", { duration: reduced ? 0 : 0.35, ease: "power3.out" });
  let cards = [];
  let lean = [];
  let lastX = rail.scrollLeft;
  let lastT = performance.now();
  let settle = null;

  rail.addEventListener(
    "scroll",
    () => {
      const max = rail.scrollWidth - rail.clientWidth;
      toBar(Math.max(0.06, max > 0 ? rail.scrollLeft / max : 0));
      if (reduced) return;
      const now = performance.now();
      const v = (rail.scrollLeft - lastX) / Math.max(1, now - lastT); // px per ms
      lastX = rail.scrollLeft;
      lastT = now;
      const skew = gsap.utils.clamp(-6, 6, -v * 2.2);
      lean.forEach((to) => to(skew));
      settle?.kill();
      settle = gsap.delayedCall(0.12, () => lean.forEach((to) => to(0)));
    },
    { passive: true },
  );

  function tilt(card) {
    const rx = gsap.quickTo(card, "rotationX", { duration: 0.6, ease: "power3.out" });
    const ry = gsap.quickTo(card, "rotationY", { duration: 0.6, ease: "power3.out" });
    gsap.set(card, { transformPerspective: 900 });
    card.addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") return;
      const r = card.getBoundingClientRect();
      const nx = (e.clientX - r.left) / r.width;
      const ny = (e.clientY - r.top) / r.height;
      rx((0.5 - ny) * 7);
      ry((nx - 0.5) * 9);
      card.style.setProperty("--gx", `${nx * 100}%`);
      card.style.setProperty("--gy", `${ny * 100}%`);
    });
    card.addEventListener("pointerleave", () => {
      rx(0);
      ry(0);
    });
  }

  return {
    refresh() {
      cards = Array.from(rail.querySelectorAll("[data-news-card] > a"));
      lean = cards.map((c) => gsap.quickTo(c, "skewX", { duration: 0.5, ease: "power3.out" }));
      if (!reduced) cards.forEach(tilt);
      rail.dispatchEvent(new Event("scroll"));
    },
  };
}
