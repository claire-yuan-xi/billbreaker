/** The optional "about you" questions: choice chips, free text and the state select. */
export function initAboutYou(container) {
  const fields = Array.from(container.querySelectorAll("[data-question]"));
  let profile = {};

  function paint() {
    for (const field of fields) {
      const value = profile[field.dataset.question] ?? "";
      const chips = Array.from(field.querySelectorAll("[data-choice]"));
      chips.forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.choice === value)));
      const free = field.querySelector("[data-free]");
      if (free) free.value = chips.some((c) => c.dataset.choice === value) ? "" : value;
      const select = field.querySelector("[data-answer]");
      if (select) select.value = value;
    }
  }

  for (const field of fields) {
    const key = field.dataset.question;
    field.querySelectorAll("[data-choice]").forEach((chip) =>
      chip.addEventListener("click", () => {
        profile[key] = profile[key] === chip.dataset.choice ? "" : chip.dataset.choice;
        paint();
      }),
    );
    field.querySelector("[data-free]")?.addEventListener("input", (e) => {
      profile[key] = e.target.value;
      field.querySelectorAll("[data-choice]").forEach((c) => c.setAttribute("aria-pressed", "false"));
    });
    field.querySelector("[data-answer]")?.addEventListener("change", (e) => {
      profile[key] = e.target.value;
    });
  }

  return {
    get profile() {
      return { ...profile };
    },
    set(next) {
      profile = { ...next };
      paint();
    },
  };
}
