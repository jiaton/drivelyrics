import { describe, expect, it } from "vitest";
import { candidatesOf } from "./listenApi";

describe("candidatesOf", () => {
  it("puts the recognised song first, then other releases of the same audio", () => {
    const match = {
      matched: true,
      exact: true,
      title: "Những Kì Vọng Đẹp Nhất",
      artist: "Thất Dạ",
      track_id: "feed:a",
      alternatives: [{ title: "最美的期待", artist: "周笔畅", track_id: "feed:b" }],
    };
    expect(candidatesOf(match).map((c) => c.track_id)).toEqual(["feed:a", "feed:b"]);
    expect(candidatesOf({ matched: false, exact: false, alternatives: [] })).toEqual([]);
  });
});
