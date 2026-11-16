import { wirePress } from "../lib/press.js";

/** Keeps the button label in step with the picked amount, and blocks double submits. */
function initDonate(form) {
  if (!form) return;
  const button = form.querySelector("[data-donate-submit]");
  form.addEventListener("change", () => {
    button.textContent = `Donate $${form.elements.amount.value}`;
  });
  form.addEventListener("submit", () => {
    // Disable after the browser has read the form, or the click is lost.
    setTimeout(() => {
      button.disabled = true;
      button.textContent = "Opening";
    });
  });
}

initDonate(document.querySelector("[data-donate]"));
wirePress();
