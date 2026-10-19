import { gsap, prefersReducedMotion } from "../lib/motion.js";
import { closeModal, openModal, wireModal } from "../lib/modal.js";
import { readProfile, saveProfile } from "../lib/reader-profile.js";
import { initAboutYou } from "./about-you.js";
import { initStateCombobox } from "./state-combobox.js";

// Bill number format: 1-5 letters (HB, S, HR, SB), optional space, dot or dash, 1-6 digits.
const BILL_NO_RE = /^[A-Za-z]{1,5}[.\s-]?\d{1,6}$/;
const MIN_PASTE = 100;

/** "Which bill" then "About you", ending on the bill page. Returns open(mode). */
export function initSearchDialog(dialog, stateNames) {
  wireModal(dialog);
  const stepBill = dialog.querySelector('[data-step="bill"]');
  const stepAbout = dialog.querySelector('[data-step="about"]');
  const billInput = dialog.querySelector("[data-bill-input]");
  const hint = dialog.querySelector("[data-bill-hint]");
  const paste = dialog.querySelector("[data-paste-input]");
  const pasteCount = dialog.querySelector("[data-paste-count]");
  const next = dialog.querySelector("[data-continue]");
  const combo = initStateCombobox(dialog.querySelector("[data-combobox]"), () => validate());
  const about = initAboutYou(stepAbout);
  let mode = "number";

  function animateStep(step) {
    if (prefersReducedMotion()) return;
    gsap.fromTo(
      step.querySelector("[data-step-body]").children,
      { opacity: 0, y: 14 },
      { opacity: 1, y: 0, duration: 0.5, ease: "power3.out", stagger: 0.04 },
    );
  }

  function validate() {
    const trimmed = billInput.value.trim();
    const bad = trimmed.length > 0 && !BILL_NO_RE.test(trimmed);
    billInput.setAttribute("aria-invalid", String(bad));
    hint.textContent = bad ? "Try something like HR 1234" : "Like HR 1234";
    hint.classList.toggle("text-destructive", bad);
    hint.classList.toggle("text-muted-foreground", !bad);
    pasteCount.textContent = `${paste.value.length.toLocaleString()} / 50,000`;
    const ok = mode === "number" ? BILL_NO_RE.test(trimmed) : paste.value.trim().length >= MIN_PASTE;
    next.disabled = !ok;
    return ok;
  }

  function setMode(m) {
    mode = m;
    dialog.querySelectorAll("[data-mode]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.mode === m)));
    dialog.querySelectorAll("[data-mode-panel]").forEach((p) => p.classList.toggle("hidden", p.dataset.modePanel !== m));
    validate();
    animateStep(stepBill);
    (m === "number" ? billInput : paste).focus();
  }

  function showStep(name) {
    stepBill.classList.toggle("hidden", name !== "bill");
    stepAbout.classList.toggle("hidden", name !== "about");
    animateStep(name === "bill" ? stepBill : stepAbout);
  }

  function go(withProfile) {
    saveProfile(withProfile ? about.profile : {});
    closeModal(dialog);
    const q =
      mode === "number"
        ? new URLSearchParams({ state: combo.value, number: billInput.value.trim() })
        : new URLSearchParams({ state: "US", text: paste.value });
    window.location.href = `/bill?${q}`;
  }

  dialog.querySelectorAll("[data-mode]").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
  dialog.querySelectorAll("[data-example]").forEach((b) =>
    b.addEventListener("click", () => {
      billInput.value = b.dataset.example;
      validate();
    }),
  );
  billInput.addEventListener("input", validate);
  paste.addEventListener("input", validate);
  stepBill.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validate()) return;
    // A state bill tells us where they live; prefill it, but they can change it.
    const profile = about.profile;
    if (mode === "number" && combo.value !== "US" && !profile.state) {
      about.set({ ...profile, state: stateNames[combo.value] ?? "" });
    }
    showStep("about");
  });
  dialog.querySelector("[data-back]").addEventListener("click", () => showStep("bill"));
  dialog.querySelector('[data-go="skip"]').addEventListener("click", () => go(false));
  dialog.querySelector('[data-go="explain"]').addEventListener("click", () => go(true));

  return function open(m = "number") {
    about.set(readProfile());
    stepBill.classList.remove("hidden");
    stepAbout.classList.add("hidden");
    openModal(dialog);
    setMode(m);
  };
}
