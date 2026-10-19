import { show } from "../lib/dom.js";
import {
  clearWatchlist,
  fromRemoteItems,
  getDeviceId,
  isValidDeviceId,
  mergeWatchlist,
  parseBackup,
  readWatchlist,
  serializeBackup,
  setDeviceId,
} from "../lib/watchlist.js";
import { cloudEnabled, pullCloud, pushAll } from "./cloud.js";

const MAX_FILE = 1_000_000;

/**
 * Backup and restore for saved bills. Everything lives in localStorage; when cloud sync
 * is on, an opaque per-device code also keeps a copy for cross-device recovery.
 */
export function initBackupTools(root, notify) {
  const file = root.querySelector("[data-backup-file]");
  const code = root.querySelector("[data-device-code]");
  const adoptInput = root.querySelector("[data-adopt-input]");
  const adoptButton = root.querySelector('[data-backup="adopt"]');
  let items = [];
  let cloud = false;

  cloudEnabled().then((on) => {
    cloud = on;
    show(root.querySelector("[data-cloud-off]"), !on);
    show(root.querySelector("[data-cloud-on]"), on);
    if (on) code.textContent = getDeviceId();
  });

  const plural = (n) => `${n} bill${n === 1 ? "" : "s"}`;

  const actions = {
    download() {
      if (!items.length) return notify("Nothing to back up yet. Save a bill first.");
      try {
        const url = URL.createObjectURL(new Blob([serializeBackup(items)], { type: "application/json" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `billbreaker-saved-bills-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        notify(`Downloaded a backup of ${plural(items.length)}.`);
      } catch {
        notify("The download didn't start. Try Copy backup instead.");
      }
    },
    copy() {
      if (!items.length) return notify("Nothing to copy yet. Save a bill first.");
      navigator.clipboard
        .writeText(serializeBackup(items))
        .then(() => notify("Backup copied. Paste it into a note or email to keep it."))
        .catch(() => notify("Your browser blocked the clipboard. Use Download backup instead."));
    },
    restore() {
      file.click();
    },
    clear() {
      if (!items.length) return;
      if (!window.confirm(`Remove all ${items.length} saved bills from this browser?`)) return;
      clearWatchlist();
      notify(cloud ? "Cleared on this device. The cloud copy is kept, so your code can restore it." : "All saved bills cleared.");
    },
    "copy-code"() {
      navigator.clipboard
        .writeText(getDeviceId())
        .then(() => notify("Recovery code copied. Keep it somewhere private."))
        .catch(() => notify("Could not copy the code."));
    },
    async adopt() {
      const next = adoptInput.value.trim().toLowerCase();
      if (!isValidDeviceId(next)) return notify("That isn't a valid recovery code.");
      if (!setDeviceId(next)) return notify("Could not save the code in this browser.");
      code.textContent = next;
      adoptInput.value = "";
      adoptButton.disabled = true;
      adoptButton.textContent = "Syncing";
      try {
        const r = await pullCloud(next);
        const result = mergeWatchlist(fromRemoteItems(r.items));
        notify(`Code linked. Pulled ${result.added} new, ${result.merged} updated.`);
      } catch (e) {
        notify(e.message || "Couldn't reach the cloud copy.");
      } finally {
        adoptButton.textContent = "Link and pull";
      }
    },
  };

  root.querySelectorAll("[data-backup]").forEach((b) => b.addEventListener("click", () => actions[b.dataset.backup]()));
  adoptInput.addEventListener("input", () => (adoptButton.disabled = !adoptInput.value.trim()));

  file.addEventListener("change", async () => {
    const f = file.files?.[0];
    file.value = "";
    if (!f) return;
    if (f.size > MAX_FILE) return notify("That file is too large (over 1 MB) to be a Bill Breaker backup.");
    try {
      const result = mergeWatchlist(parseBackup(await f.text()));
      notify(`Restored ${result.added} new and updated ${result.merged}. You now have ${result.total} saved.`);
      if (cloud) pushAll(getDeviceId(), readWatchlist()).catch(() => {});
    } catch {
      notify("That file isn't a Bill Breaker backup.");
    }
  });

  return {
    render(next) {
      items = next;
      root.querySelectorAll("[data-needs-items]").forEach((b) => (b.disabled = items.length === 0));
    },
  };
}
