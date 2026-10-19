import { gsap } from "../lib/motion.js";

/**
 * Calls onChange(true) while el overlaps anything matching selectors on screen,
 * and onChange(false) once it is clear. Checks a few times a second on GSAP's
 * ticker, so it keeps up with scrolling and layout changes.
 */
export function watchOverlap(el, selectors, onChange, margin = 24) {
  let frame = 0;
  let state = null;
  const query = selectors.join(",");
  gsap.ticker.add(() => {
    if (++frame % 6) return;
    const a = el.getBoundingClientRect();
    let hit = false;
    for (const other of document.querySelectorAll(query)) {
      const b = other.getBoundingClientRect();
      if (
        a.right + margin > b.left &&
        a.left - margin < b.right &&
        a.bottom + margin > b.top &&
        a.top - margin < b.bottom
      ) {
        hit = true;
        break;
      }
    }
    if (hit !== state) {
      state = hit;
      onChange(hit);
    }
  });
}
