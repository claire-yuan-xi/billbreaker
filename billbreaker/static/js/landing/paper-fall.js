import { gsap } from "../lib/motion.js";

/**
 * Falling-paper motion. Scroll only sets how far down the page the sheet should
 * be; a small simulation moves it there the way paper falls through air: it
 * lags behind fast scrolls, swings side to side as it drops, banks into each
 * swing, and flutters harder the faster it falls.
 */
export function startPaperFall({ wrap, sheet, sheen }) {
  const setY = gsap.quickSetter(wrap, "y", "px");
  const setX = gsap.quickSetter(wrap, "x", "px");
  const setRot = gsap.quickSetter(wrap, "rotation", "deg");
  const setRX = gsap.quickSetter(sheet, "rotationX", "deg");
  const setRY = gsap.quickSetter(sheet, "rotationY", "deg");
  const setSkew = gsap.quickSetter(sheet, "skewY", "deg");
  const setSheen = sheen ? gsap.quickSetter(sheen, "opacity") : null;

  let progress = 0;
  let y = -1;
  let vy = 0;
  let phase = 0.6;
  let flutter = 0;
  let time = 0;

  const tick = (_t, deltaMs) => {
    const dt = Math.min(deltaMs / 1000, 0.05);
    time += dt;
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const target = vh * (0.2 + progress * 0.52);
    if (y < 0) y = target;

    // Drag-limited approach: it settles toward where the scroll says it should
    // be, but never faster than paper can fall (or float back up).
    const prev = y;
    const want = (target - y) * 2.4;
    const terminal = vh * 0.9;
    vy += (Math.max(-terminal, Math.min(terminal, want)) - vy) * Math.min(1, dt * 6);
    y += vy * dt;
    const speed = Math.abs(y - prev) / Math.max(dt, 1e-4);

    // Sway advances with distance fallen, plus a slow idle drift in still air.
    phase += (Math.abs(y - prev) / vh) * 7.5 + dt * 0.35;
    const swing = Math.sin(phase);
    const swingVel = Math.cos(phase);
    flutter += (Math.min(1, speed / (vh * 0.6)) - flutter) * Math.min(1, dt * 3);

    setY(y);
    setX(swing * vw * 0.035);
    // Paper banks into the direction it is gliding, like a leaf.
    setRot(swingVel * (8 + flutter * 10) + Math.sin(time * 0.7) * 1.5);
    setRX(14 + Math.sin(time * 1.6 + phase) * (6 + flutter * 22));
    setRY(-swingVel * (12 + flutter * 14));
    setSkew(Math.sin(time * 3.1) * flutter * 2.5);
    // Light catches the sheet as it tips toward the sky.
    setSheen?.(0.15 + Math.max(0, swingVel) * 0.35 + flutter * 0.2);
  };
  gsap.ticker.add(tick);

  return {
    setProgress(p) {
      progress = p;
    },
  };
}
