export type Clock = "local" | "utc";
export const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
export const zoneFor = (clock: Clock) =>
  clock === "utc" ? "UTC" : browserZone;
export function timeLabel(iso: string, clock: Clock) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: zoneFor(clock),
  }).format(new Date(iso));
}
export function inputDate(iso: string, clock: Clock): string {
  const date = new Date(iso);
  return new Date(
    date.getTime() - (clock === "utc" ? 0 : date.getTimezoneOffset() * 60_000),
  )
    .toISOString()
    .slice(0, 16);
}
export function inputISO(input: string, clock: Clock): string {
  return new Date(clock === "utc" ? `${input}Z` : input).toISOString();
}
