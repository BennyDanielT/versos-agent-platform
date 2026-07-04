// Tiny classnames helper. Dependency-free (no clsx/tailwind-merge) so the demo has
// nothing extra to install — join truthy class fragments, collapse whitespace.
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}
