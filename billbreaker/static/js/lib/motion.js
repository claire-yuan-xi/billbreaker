// GSAP and ScrollTrigger are loaded as plain scripts in base.html; this module hands them out.
export const gsap = window.gsap;
export const ScrollTrigger = window.ScrollTrigger;

if (gsap && ScrollTrigger) gsap.registerPlugin(ScrollTrigger);

export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
