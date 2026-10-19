import { getJSON, postJSON } from "../lib/api.js";
import { getDeviceId, removeBill, saveBill } from "../lib/watchlist.js";

// A failed cloud write is not fatal: the local list is the source of truth and the
// next bulk push or pull reconciles it.
const ignore = () => {};
let status = null;

/** True once the server says cloud sync is on; false (this browser only) otherwise. */
export function cloudEnabled() {
  status ??= getJSON("/api/watchlist/status")
    .then((r) => Boolean(r.cloud))
    .catch(() => false);
  return status;
}

/** Saves locally first, then mirrors to the cloud copy when it exists. */
export async function saveAndSync(state, billNo, title) {
  saveBill(state, billNo, title);
  if (await cloudEnabled()) {
    postJSON("/api/watchlist/push", { device_id: getDeviceId(), state, bill_no: billNo, title }).catch(ignore);
  }
}

export async function removeAndSync(item) {
  removeBill(item.state, item.bill_no);
  if (await cloudEnabled()) {
    postJSON("/api/watchlist/remove", { device_id: getDeviceId(), state: item.state, bill_no: item.bill_no }).catch(ignore);
  }
}

export const pullCloud = (deviceId) => postJSON("/api/watchlist/pull", { device_id: deviceId });
export const pushAll = (deviceId, items) => postJSON("/api/watchlist/bulk", { device_id: deviceId, items });
