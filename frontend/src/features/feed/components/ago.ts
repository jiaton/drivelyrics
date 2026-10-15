import { fill } from "../../../i18n/rich";

type Words = { agoSeconds: string; agoMinutes: string; agoHours: string };

/** "12 s ago" for a unix-seconds timestamp. */
export function ago(words: Words, at: number, now = Date.now() / 1000): string {
  const s = Math.max(0, Math.round(now - at));
  if (s < 90) return fill(words.agoSeconds, { n: String(s) });
  if (s < 90 * 60) return fill(words.agoMinutes, { n: String(Math.round(s / 60)) });
  return fill(words.agoHours, { n: String(Math.round(s / 3600)) });
}
