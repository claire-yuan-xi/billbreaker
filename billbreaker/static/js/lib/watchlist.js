// Saved bills live in localStorage, with a portable backup format.
// Cloud sync is optional and keyed by an opaque per-device id.

export const WATCH_KEY = "bb_watchlist_v1";
export const DEVICE_KEY = "bb_device_id_v1";
const BACKUP_VERSION = 1;
const CHANGE_EVENT = "bb:watchlist";

const STATE_RE = /^[A-Z]{2,4}$/;
// "HB 12", "S 3000A", or an older federal bill with its Congress: "HR 5376 (117th)".
const BILL_NO_RE = /^[A-Za-z]{1,8}[.\s-]?\d{1,6}[A-Za-z]?(?: \(\d{1,3}(?:st|nd|rd|th)\))?$/;
const DEVICE_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidItem(x) {
  return (
    !!x &&
    typeof x === "object" &&
    typeof x.state === "string" &&
    STATE_RE.test(x.state) &&
    typeof x.bill_no === "string" &&
    BILL_NO_RE.test(x.bill_no) &&
    typeof x.title === "string" &&
    typeof x.ts === "number" &&
    Number.isFinite(x.ts)
  );
}

export function isValidDeviceId(x) {
  return typeof x === "string" && DEVICE_ID_RE.test(x);
}

export function readWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCH_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(isValidItem) : [];
  } catch {
    return [];
  }
}

function writeWatchlist(items) {
  try {
    localStorage.setItem(WATCH_KEY, JSON.stringify(items.slice(0, 200)));
  } catch {
    // quota or storage disabled
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** Calls cb whenever the saved list changes, in this tab or another one. */
export function subscribeWatchlist(cb) {
  window.addEventListener(CHANGE_EVENT, cb);
  window.addEventListener("storage", (e) => {
    if (e.key === WATCH_KEY || e.key === null) cb();
  });
}

const same = (a, state, billNo) => a.state === state && a.bill_no === billNo;

export function isSaved(state, billNo, list = readWatchlist()) {
  return list.some((w) => same(w, state, billNo));
}

export function saveBill(state, billNo, title) {
  const item = { state, bill_no: billNo, title, ts: Date.now() };
  writeWatchlist([item, ...readWatchlist().filter((w) => !same(w, state, billNo))]);
  return item;
}

export function removeBill(state, billNo) {
  writeWatchlist(readWatchlist().filter((w) => !same(w, state, billNo)));
}

/** Puts a removed item back where it was (for Undo). */
export function restoreBill(item) {
  const rest = readWatchlist().filter((w) => !same(w, item.state, item.bill_no));
  writeWatchlist([...rest, item].sort((a, b) => b.ts - a.ts));
}

/** Fills in the real title once it is known, without reordering. */
export function retitleBill(state, billNo, title) {
  const list = readWatchlist();
  const hit = list.find((w) => same(w, state, billNo));
  if (!hit || !title || hit.title === title) return;
  writeWatchlist(list.map((w) => (w === hit ? { ...w, title } : w)));
}

export function clearWatchlist() {
  try {
    localStorage.removeItem(WATCH_KEY);
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function getDeviceId() {
  try {
    const existing = localStorage.getItem(DEVICE_KEY);
    if (isValidDeviceId(existing)) return existing;
    const next = crypto.randomUUID();
    localStorage.setItem(DEVICE_KEY, next);
    return next;
  } catch {
    return "";
  }
}

export function setDeviceId(id) {
  if (!isValidDeviceId(id)) return false;
  try {
    localStorage.setItem(DEVICE_KEY, id.toLowerCase());
    return true;
  } catch {
    return false;
  }
}

export function serializeBackup(items = readWatchlist()) {
  const backup = { version: BACKUP_VERSION, exportedAt: Date.now(), items };
  const dev = localStorage.getItem(DEVICE_KEY) || "";
  if (isValidDeviceId(dev)) backup.device_id = dev;
  return JSON.stringify(backup, null, 2);
}

export function parseBackup(json) {
  const data = JSON.parse(json);
  if (data && Array.isArray(data.items)) return data.items.filter(isValidItem);
  if (Array.isArray(data)) return data.filter(isValidItem);
  throw new Error("Not a valid watchlist backup");
}

/** Merges imported items with the current list, de-duplicated by (state, bill_no). */
export function mergeWatchlist(incoming) {
  const byKey = new Map(readWatchlist().map((i) => [`${i.state}|${i.bill_no}`, i]));
  let added = 0;
  let merged = 0;
  let skipped = 0;
  for (const item of incoming) {
    if (!isValidItem(item)) {
      skipped++;
      continue;
    }
    const key = `${item.state}|${item.bill_no}`;
    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, item);
      added++;
    } else if (item.ts > existing.ts || (existing.title === "" && item.title)) {
      byKey.set(key, { ...existing, ...item, ts: Math.max(existing.ts, item.ts) });
      merged++;
    } else {
      skipped++;
    }
  }
  const next = [...byKey.values()].sort((a, b) => b.ts - a.ts);
  writeWatchlist(next);
  return { added, merged, skipped, total: next.length };
}

/** Converts rows from the cloud copy into local items. */
export function fromRemoteItems(rows) {
  return rows.map((i) => ({
    state: i.state,
    bill_no: i.bill_no,
    title: i.title,
    ts: new Date(i.added_at).getTime() || Date.now(),
  }));
}
