// Counts clicks on links and buttons for the stats page. Sends nothing else.

const TARGETS = "a[href], button, [role='button'], summary, input[type='submit']";

function send() {
  try {
    if (!navigator.sendBeacon?.("/api/hit")) {
      fetch("/api/hit", { method: "POST", keepalive: true }).catch(() => {});
    }
  } catch {
    // A missed count is fine.
  }
}

document.addEventListener(
  "click",
  (event) => {
    if (event.target instanceof Element && event.target.closest(TARGETS)) send();
  },
  { capture: true, passive: true },
);
