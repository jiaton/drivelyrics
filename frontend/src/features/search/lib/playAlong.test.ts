import { describe, expect, it } from "vitest";
import { clockAt, resumePosition, RESUME_GRACE_MS } from "./playAlong";

describe("play-along", () => {
  const anchor = { song: "lrclib:1", positionMs: 60_000, at: 1_000_000 };

  it("carries on where the song would be now", () => {
    expect(resumePosition(anchor, "lrclib:1", 200_000, 1_000_000 + 45_000)).toBe(105_000);
  });

  it("ignores another song's anchor and a song that's over", () => {
    expect(resumePosition(anchor, "lrclib:2", 200_000, 1_000_100)).toBeNull();
    expect(resumePosition(anchor, "lrclib:1", 200_000, 1_000_000 + 140_000 + RESUME_GRACE_MS + 1)).toBeNull();
    expect(resumePosition(null, "lrclib:1", 200_000, 0)).toBeNull();
  });

  it("builds a following clock from a position", () => {
    const clock = clockAt(61_234.6, 500);
    expect([clock.is_playing, clock.progress_ms, clock.receivedAtPerf]).toEqual([true, 61_235, 500]);
  });
});
