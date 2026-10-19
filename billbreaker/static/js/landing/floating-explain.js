import { gsap, ScrollTrigger } from "../lib/motion.js";

/** Shows the floating "Explain a bill" button once the hero button has scrolled away. */
export function initFloatingExplain(button, after) {
  gsap.set(button, { autoAlpha: 0, y: 24 });
  const show = (on) =>
    gsap.to(button, {
      autoAlpha: on ? 1 : 0,
      y: on ? 0 : 24,
      duration: 0.45,
      ease: "power3.out",
      overwrite: "auto",
    });
  ScrollTrigger.create({
    trigger: after,
    start: "bottom 30%",
    onEnter: () => show(true),
    onLeaveBack: () => show(false),
  });
}
