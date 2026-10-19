import { gsap, ScrollTrigger, prefersReducedMotion } from "../lib/motion.js";
import { mountPhoto } from "./photo-scene.js";

// Depth (red) and sky mask (green) for the same photo; regenerate if the photo changes.
const DEPTH = "/static/images/capitol-depth.png";

/** The Capitol photo, its WebGL depth pass, and the hero's entrance and scroll motion. */
export function initCapitolHero(section) {
  const img = section.querySelector("[data-photo]");
  const photo = section.querySelector("[data-hero-photo]");
  const copy = section.querySelector("[data-hero-copy]");
  const canvas = section.querySelector("[data-hero-canvas]");

  const markLoaded = () => (img.dataset.loaded = "true");
  if (img.complete && img.naturalWidth > 0) markLoaded();
  img.addEventListener("load", markLoaded);
  img.addEventListener("error", () => img.remove());

  mountDepthPass(section, canvas, img.currentSrc || img.src);
  if (prefersReducedMotion()) return;

  // Slow establishing push-in, like a camera on a long lens settling.
  gsap.fromTo(img, { scale: 1.16 }, { scale: 1.04, duration: 7, ease: "expo.out" });
  gsap.fromTo(
    section.querySelectorAll("[data-hero-line]"),
    { yPercent: 110, opacity: 0 },
    { yPercent: 0, opacity: 1, duration: 1.2, ease: "expo.out", stagger: 0.1, delay: 0.3 },
  );
  gsap.fromTo(
    section.querySelectorAll("[data-hero-fade]"),
    { opacity: 0, y: 16 },
    { opacity: 1, y: 0, duration: 0.9, ease: "power2.out", stagger: 0.08, delay: 0.8 },
  );

  // Scroll: the photo sinks (parallax), the light turns to dusk, the copy lifts away.
  const scrub = { trigger: section, start: "top top", end: "bottom top", scrub: 0.6 };
  gsap.to(photo, { yPercent: 14, ease: "none", scrollTrigger: scrub });
  gsap.to(section.querySelector("[data-dusk]"), { opacity: 1, ease: "none", scrollTrigger: scrub });
  gsap.to(copy, {
    yPercent: -16,
    opacity: 0,
    ease: "none",
    scrollTrigger: { ...scrub, end: "70% top", scrub: 0.8 },
  });

  // A little depth under the pointer.
  const toX = gsap.quickTo(photo, "x", { duration: 1.6, ease: "power3.out" });
  const toR = gsap.quickTo(photo, "rotationY", { duration: 1.6, ease: "power3.out" });
  window.addEventListener(
    "pointermove",
    (e) => {
      const nx = e.clientX / window.innerWidth - 0.5;
      toX(nx * -24);
      toR(nx * 1.2);
    },
    { passive: true },
  );
}

/** Once the WebGL pass draws its first frame it owns depth, camera motion, light and dusk. */
function mountDepthPass(section, canvas, src) {
  let handle;
  try {
    handle = mountPhoto(canvas, {
      src,
      depthSrc: DEPTH,
      focus: [0.5, 0.62],
      // Matches the <img> object-position: centered across, 40% down.
      anchorFor: () => [0.5, 0.6],
      reducedMotion: prefersReducedMotion(),
      onReady: () => (section.dataset.deep = "true"),
      onError: () => (section.dataset.deep = "false"),
    });
  } catch {
    return;
  }
  const st = ScrollTrigger.create({
    trigger: section,
    start: "top top",
    end: "bottom top",
    onUpdate: (self) => handle.setProgress(self.progress),
  });
  handle.setProgress(st.progress);
}
