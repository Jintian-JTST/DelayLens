import type { AskResponse } from "./api";

/** Why Ask DelayLens is switched off up front, or null when it can be used. */
export type AskOffReason = "snapshot" | "gemini" | null;

/**
 * The backend appends "Offline snapshot frozen ... UTC; not live data." to the
 * curve basis in snapshot mode (backend/app/snapshot_files.py). That mode has
 * no live services, so Ask cannot work there.
 */
export function isSnapshotBasis(basis: string | null | undefined): boolean {
  return /offline snapshot/i.test(basis ?? "");
}

/**
 * Next Ask state after a curve basis or Ask response is seen. Snapshot mode is
 * definitive and sticky; a gemini_unavailable reply turns Ask off until the
 * user chooses to try again.
 */
export function nextAskOffReason(
  current: AskOffReason,
  seen: { basis?: string | null; askStatus?: AskResponse["status"] },
): AskOffReason {
  if (current === "snapshot" || isSnapshotBasis(seen.basis)) return "snapshot";
  if (seen.askStatus === "gemini_unavailable") return "gemini";
  if (seen.askStatus) return null;
  return current;
}

export function askOffNotice(reason: AskOffReason): string {
  if (reason === "snapshot")
    return "Ask is off in offline snapshot mode. Use the journey form below.";
  if (reason === "gemini")
    return "Ask DelayLens is unavailable on this server right now. Use the journey form below.";
  return "";
}
