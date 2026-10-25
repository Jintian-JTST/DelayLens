import type { AskResponse, Health } from "./api";

/**
 * Why Ask DelayLens is switched off up front, or null when it can be used.
 * - "no_key": the server reports no Gemini key (GET /api/health ask_available=false).
 * - "unchecked": the health check failed or did not report the flag, so we
 *   cannot say whether Ask works; it stays off rather than look connected.
 * - "gemini": a question came back gemini_unavailable (bad key, quota, network).
 *
 * Snapshot mode alone does not turn Ask off: the backend answers from the same
 * snapshot curve whenever it has a Gemini key and network.
 */
export type AskOffReason = "no_key" | "unchecked" | "gemini" | null;

/**
 * Ask state from GET /api/health. Pass null when the request failed (network
 * error or non-200). Only an explicit `ask_available: true` enables Ask; it
 * means a key is configured, not that Gemini has been reached.
 */
export function askOffFromHealth(
  health: Pick<Health, "ask_available"> | null | undefined,
): AskOffReason {
  if (health?.ask_available === true) return null;
  if (health?.ask_available === false) return "no_key";
  return "unchecked";
}

/**
 * Next Ask state after an Ask response. "no_key" is definitive for this
 * server; a gemini_unavailable reply turns Ask off until the user tries again.
 */
export function nextAskOffReason(
  current: AskOffReason,
  askStatus: AskResponse["status"] | undefined,
): AskOffReason {
  if (current === "no_key" || current === "unchecked") return current;
  if (askStatus === "gemini_unavailable") return "gemini";
  if (askStatus) return null;
  return current;
}

export function askOffNotice(reason: AskOffReason): string {
  if (reason === "no_key")
    return "Ask DelayLens needs a Gemini API key on the server, and this server has none configured. The journey form below works without it.";
  if (reason === "unchecked")
    return "We could not check whether Ask DelayLens is available on this server, so it is off. The journey form below works without it.";
  if (reason === "gemini")
    return "Ask DelayLens could not reach Gemini just now. The journey form below still works.";
  return "";
}

export function askPlaceholder(reason: AskOffReason): string {
  if (reason === "no_key") return "Ask needs a Gemini key on the server";
  if (reason === "unchecked") return "Ask availability could not be checked";
  if (reason === "gemini") return "Ask is unavailable right now";
  return "“I need to be at Tottenham Court Road by 5pm…”";
}
