import { describe, expect, it } from "vitest";
import { computeActiveIndex } from "./activeIndex";
import type { LyricLine } from "../types";

const lines: LyricLine[] = [
  { t: 0, text: "a" },
  { t: 1000, text: "b" },
  { t: 2000, text: "c" },
];

describe("computeActiveIndex", () => {
  it("returns -1 before the first cue", () => {
    expect(computeActiveIndex(lines, -1)).toBe(-1);
  });

  it("returns the index of the last cue at or before currentMs", () => {
    expect(computeActiveIndex(lines, 0)).toBe(0);
    expect(computeActiveIndex(lines, 999)).toBe(0);
    expect(computeActiveIndex(lines, 1000)).toBe(1);
    expect(computeActiveIndex(lines, 1500)).toBe(1);
  });

  it("returns the last index once past every cue", () => {
    expect(computeActiveIndex(lines, 999999)).toBe(2);
  });

  it("returns -1 for an empty line list", () => {
    expect(computeActiveIndex([], 5000)).toBe(-1);
  });

  it("is exact at a cue's own timestamp (boundary is inclusive)", () => {
    expect(computeActiveIndex(lines, 2000)).toBe(2);
  });
});
