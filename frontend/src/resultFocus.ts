/**
 * Submitting the journey form unmounts the previous result, so keyboard focus
 * falls back to the page top. After a user-triggered submit, the next result
 * that appears should receive focus once.
 */
export function nextResultFocus(
  pending: boolean,
  hasResult: boolean,
): { focus: boolean; pending: boolean } {
  if (!pending) return { focus: false, pending: false };
  if (!hasResult) return { focus: false, pending: true };
  return { focus: true, pending: false };
}
