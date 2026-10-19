import { ScrollTrigger } from "../lib/motion.js";

/** The nav floats over the Capitol in white, then turns solid once the hero has gone. */
export function initSiteHeader(header, hero) {
  ScrollTrigger.create({
    trigger: hero,
    start: "bottom 120px",
    onEnter: () => (header.dataset.solid = "true"),
    onLeaveBack: () => (header.dataset.solid = "false"),
  });
}
