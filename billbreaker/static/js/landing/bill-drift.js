import { gsap, ScrollTrigger, prefersReducedMotion } from "../lib/motion.js";
import { startPaperFall } from "./paper-fall.js";
import { watchOverlap } from "./overlap-watch.js";

/**
 * A printed bill that drifts down the page as you scroll, as if it fell from the
 * dome. It never takes pointer events, and it fades out whenever it would sit
 * over anything in avoid (sections or buttons).
 */
export function initBillDrift(wrap, avoid) {
  if (prefersReducedMotion()) return;
  const sheet = wrap.querySelector("[data-bill-sheet]");
  const fall = startPaperFall({ wrap, sheet, sheen: wrap.querySelector("[data-bill-sheen]") });
  const page = ScrollTrigger.create({
    trigger: document.documentElement,
    start: "top top",
    end: "bottom bottom",
    onUpdate: (self) => fall.setProgress(self.progress),
  });
  fall.setProgress(page.progress);
  // Measured against the sheet itself (it is fixed, so its rect never goes stale).
  watchOverlap(sheet, avoid, (hit) =>
    gsap.to(wrap, { autoAlpha: hit ? 0 : 1, duration: 0.6, ease: "power2.out", overwrite: "auto" }),
  );
}
