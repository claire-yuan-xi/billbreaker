/** Searchable jurisdiction picker with arrow-key navigation. Calls onChange(code). */
export function initStateCombobox(root, onChange) {
  const button = root.querySelector("[data-combobox-button]");
  const label = root.querySelector("[data-combobox-label]");
  const panel = root.querySelector("[data-combobox-panel]");
  const filter = root.querySelector("[data-combobox-filter]");
  const none = root.querySelector("[data-combobox-none]");
  const options = Array.from(root.querySelectorAll("li[data-code]"));
  let highlight = 0;

  const visible = () => options.filter((li) => !li.hidden);

  function paint() {
    visible().forEach((li, i) => (li.firstElementChild.dataset.active = String(i === highlight)));
    options.forEach((li) => li.querySelector("[data-selected-mark]").classList.toggle("hidden", li.dataset.code !== root.dataset.value));
  }

  function applyFilter() {
    const q = filter.value.trim().toLowerCase();
    options.forEach((li) => {
      li.hidden = !!q && !li.dataset.code.toLowerCase().includes(q) && !li.dataset.name.toLowerCase().includes(q);
    });
    none.classList.toggle("hidden", visible().length > 0);
    highlight = 0;
    paint();
  }

  function setOpen(on) {
    panel.classList.toggle("hidden", !on);
    button.setAttribute("aria-expanded", String(on));
    if (on) {
      filter.value = "";
      applyFilter();
      setTimeout(() => {
        filter.focus();
        panel.scrollIntoView({ block: "nearest" });
      }, 0);
    }
  }

  function pick(code) {
    const li = options.find((o) => o.dataset.code === code);
    if (!li) return;
    root.dataset.value = code;
    label.textContent = li.dataset.name;
    setOpen(false);
    onChange(code);
  }

  button.addEventListener("click", () => setOpen(panel.classList.contains("hidden")));
  options.forEach((li) => {
    li.firstElementChild.addEventListener("click", () => pick(li.dataset.code));
    li.firstElementChild.addEventListener("mouseenter", () => {
      highlight = visible().indexOf(li);
      paint();
    });
  });
  filter.addEventListener("input", applyFilter);
  filter.addEventListener("keydown", (e) => {
    const list = visible();
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlight = Math.min(highlight + 1, list.length - 1);
      paint();
      list[highlight]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight = Math.max(highlight - 1, 0);
      paint();
      list[highlight]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (list[highlight]) pick(list[highlight].dataset.code);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      button.focus();
    }
  });
  document.addEventListener("mousedown", (e) => {
    if (!root.contains(e.target)) setOpen(false);
  });

  return {
    get value() {
      return root.dataset.value;
    },
  };
}
