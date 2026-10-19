// Bills this browser looked up recently.

const KEY = "bb_recent_v1";

export function readRecent() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveRecent(item) {
  try {
    const rest = readRecent().filter((x) => !(x.state === item.state && x.number === item.number));
    localStorage.setItem(KEY, JSON.stringify([item, ...rest].slice(0, 8)));
  } catch {
    // ignore
  }
}

export function clearRecent() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
