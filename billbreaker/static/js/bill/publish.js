import { postJSON } from "../lib/api.js";

async function copy(text, button, idle) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Link copied.";
    setTimeout(() => (button.textContent = idle), 1800);
  } catch {
    // clipboard blocked
  }
}

/** "Share this link" copies the page address. */
export function initShareLink(button) {
  button.classList.remove("hidden");
  button.addEventListener("click", () => copy(window.location.href, button, "Share this link"));
}

/** "Publish as public page" saves a read-only snapshot at /b/<slug>. */
export function initPublish(wrap, getShare) {
  const publish = wrap.querySelector("[data-publish]");
  const open = wrap.querySelector("[data-public-link]");
  const copyButton = wrap.querySelector("[data-public-copy]");
  wrap.classList.replace("hidden", "flex");

  publish.addEventListener("click", async () => {
    publish.disabled = true;
    publish.textContent = "Publishing";
    publish.classList.remove("text-[#c4413a]");
    try {
      const { slug } = await postJSON("/api/share", getShare());
      const url = `${window.location.origin}/b/${slug}`;
      open.href = `/b/${slug}`;
      copyButton.title = url;
      copyButton.addEventListener("click", () => copy(url, copyButton, "Copy link"));
      publish.classList.add("hidden");
      open.classList.remove("hidden");
      copyButton.classList.remove("hidden");
    } catch (e) {
      publish.textContent = e.message || "Failed to publish";
      publish.classList.add("text-[#c4413a]");
      publish.disabled = false;
    }
  });
}
