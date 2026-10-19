import { clearProfile, readProfile } from "../lib/reader-profile.js";

/** Shows the reader's optional answers, with a way to forget them. */
export function initReaderStrip(strip) {
  const answers = Object.values(readProfile()).filter(Boolean);
  if (!answers.length) return;
  strip.querySelector("[data-reader-answers]").replaceChildren(
    ...answers.map((a) => {
      const chip = document.createElement("span");
      chip.className = "border border-[#d6d3ca] px-2 py-0.5 text-xs";
      chip.textContent = a;
      return chip;
    }),
  );
  strip.classList.replace("hidden", "flex");
  strip.querySelector("[data-forget]").addEventListener("click", () => {
    clearProfile();
    strip.classList.replace("flex", "hidden");
  });
}
