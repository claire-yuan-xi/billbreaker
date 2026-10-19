// The "about you" answers from the search flow. Personal data, so it lives in
// sessionStorage only: never in the URL, and gone when the tab closes.

const KEY = "bb_reader_v1";

export function readProfile() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveProfile(profile) {
  const clean = Object.fromEntries(
    Object.entries(profile).filter(([, v]) => typeof v === "string" && v.trim()),
  );
  try {
    if (Object.keys(clean).length) sessionStorage.setItem(KEY, JSON.stringify(clean));
    else sessionStorage.removeItem(KEY);
  } catch {
    // private mode: the profile just won't carry over
  }
  return clean;
}

export function clearProfile() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
