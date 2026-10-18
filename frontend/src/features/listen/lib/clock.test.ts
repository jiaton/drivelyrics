import { describe, expect, it } from "vitest";
import { clockFrom, nextListenAt, positionAt, setPosition, NEXT_SONG_SLACK_MS } from "./clock";

const match = { matched: true, title: "七里香", artist: "Jay Chou", duration_ms: 297_200, track_id: "x", position_ms: 44_740, exact: true, album: null, alternatives: [] };

describe("listen clock", () => {
  it("counts forward from where the song was when recording started", () => {
    const clock = clockFrom(match, 1_000);
    expect(positionAt(clock, 8_000)).toBe(44_740 + 7_000);
  });

  it("re-anchors on a nudge or a tapped line", () => {
    const clock = setPosition(clockFrom(match, 1_000), 60_000, 20_000);
    expect(positionAt(clock, 21_000)).toBe(61_000);
  });

  it("listens again right after the song should end", () => {
    const clock = clockFrom(match, 1_000);
    expect(nextListenAt(clock)).toBe(1_000 + (297_200 - 44_740) + NEXT_SONG_SLACK_MS);
    expect(nextListenAt({ ...clock, duration_ms: null })).toBeNull();
    // No duration: guessed from the last lyric line.
    expect(nextListenAt({ ...clock, duration_ms: null }, 250_000)).toBe(1_000 + (250_000 + 20_000 - 44_740) + NEXT_SONG_SLACK_MS);
  });
});
