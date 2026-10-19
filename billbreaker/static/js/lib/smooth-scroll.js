import { gsap, ScrollTrigger, prefersReducedMotion } from "./motion.js";

/**
 * Eased page scrolling, driven by GSAP's ticker so ScrollTrigger scrubs read the
 * same scroll position Lenis renders. Native scrolling is untouched for touch,
 * keyboard, find-in-page and anchors; off when the reader prefers reduced motion.
 * Returns the Lenis instance (or null) so dialogs can pause it.
 */
export function startSmoothScroll() {
  if (prefersReducedMotion() || !window.Lenis) return null;
  const lenis = new window.Lenis({
    lerp: 0.14,
    wheelMultiplier: 1.2,
    // The news rail and any scrollable dialog keep their own native scrolling.
    allowNestedScroll: true,
    autoRaf: false,
  });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((time) => lenis.raf(time * 1000));
  gsap.ticker.lagSmoothing(0);
  return lenis;
}
