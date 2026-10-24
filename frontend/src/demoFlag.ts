/**
 * The nav "Try demo" toggle switches to synthetic fixture data, so it is hidden
 * unless the URL opts in with `?demo=1`. The app does not use hash routing, but
 * `#demo=1` and `#/path?demo=1` are tolerated too.
 */
export function demoRequested(search: string, hash = ""): boolean {
  const fromHash = hash.replace(/^#/, "");
  const hashQuery = fromHash.includes("?")
    ? fromHash.slice(fromHash.indexOf("?") + 1)
    : fromHash;
  return [search, hashQuery].some((query) => {
    const value = new URLSearchParams(query).get("demo");
    return value === "1" || value === "true";
  });
}
