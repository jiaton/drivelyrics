/** 259000 → "4:19"; "" when unknown. */
export function formatDuration(ms: number | null) {
  if (ms == null) return "";
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
