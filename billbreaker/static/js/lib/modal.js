// Native <dialog> helpers: open as a modal, close on backdrop click or [data-dialog-close],
// and hold the page still underneath while any dialog is open.

let lenis = null;
let openCount = 0;

export function setScrollController(instance) {
  lenis = instance;
}

export function openModal(dialog) {
  if (dialog.open) return;
  dialog.showModal();
  openCount += 1;
  document.documentElement.classList.add("modal-open");
  lenis?.stop();
}

export function closeModal(dialog) {
  if (dialog.open) dialog.close();
}

export function wireModal(dialog) {
  dialog.addEventListener("close", () => {
    openCount = Math.max(0, openCount - 1);
    if (openCount === 0) {
      document.documentElement.classList.remove("modal-open");
      lenis?.start();
    }
  });
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) closeModal(dialog);
  });
  dialog.querySelectorAll("[data-dialog-close]").forEach((b) => b.addEventListener("click", () => closeModal(dialog)));
}
