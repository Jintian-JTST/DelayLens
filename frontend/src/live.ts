/**
 * Offline snapshot mode (backend started with SNAPSHOT_DIR) labels every curve
 * basis with "Offline snapshot frozen <stamp> UTC; not live data." (see
 * backend/app/snapshot_files.py). Live TfL arrivals are deliberately off then,
 * so the live panel shows a steady state instead of a retry prompt.
 */
export function isOfflineSnapshot(basis: string | null | undefined): boolean {
  return /\boffline snapshot\b/i.test(basis ?? "");
}

export const OFFLINE_LIVE_MESSAGE =
  "Offline snapshot mode: live arrivals are off. Departure estimates use the frozen snapshot.";
export const LIVE_UNAVAILABLE_MESSAGE =
  "TfL live arrivals are unavailable. Try refreshing in a moment.";
