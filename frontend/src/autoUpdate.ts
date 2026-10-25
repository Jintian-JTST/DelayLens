/** What a curve request depends on, so inputs can be compared with the last request sent. */
export const requestKey = (
  form: { routeId: string; deadline: string; walkTo: number; walkFrom: number },
  clock: string,
): string =>
  JSON.stringify([
    form.routeId,
    form.deadline,
    form.walkTo,
    form.walkFrom,
    clock,
  ]);

/**
 * Should the planner send a new curve request on its own?
 *
 * It compares the inputs with the last request that was sent (not with the last
 * successful result), so it also recovers after a failed first load, when there
 * is no result at all. Invalid inputs and a still-loading catalogue never send.
 */
export const shouldAutoRequest = (state: {
  valid: boolean;
  catalogBusy: boolean;
  key: string;
  lastKey: string | null;
}): boolean => state.valid && !state.catalogBusy && state.key !== state.lastKey;
