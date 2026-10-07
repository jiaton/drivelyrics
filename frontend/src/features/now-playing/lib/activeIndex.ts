import type { LyricLine } from "../types";

/**
 * Index of the last cue whose timestamp has passed, or -1 before the first cue.
 * Pure and side-effect free on purpose — this is the one piece of real logic in the
 * scroll-sync path worth unit testing in isolation (see activeIndex.test.ts), separate
 * from the DOM/timer wiring in LyricsView that's easiest to just eyeball.
 */
export function computeActiveIndex(lines: LyricLine[], currentMs: number): number {
  let index = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].t <= currentMs) index = i;
    else break;
  }
  return index;
}
