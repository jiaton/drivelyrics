import { describe, expect, it } from "vitest";
import { fling, releaseVelocity, rubberBand, TIME_CONSTANT_MS } from "./fling";

describe("releaseVelocity", () => {
  it("measures the last 100 ms of the drag", () => {
    const samples = [
      { y: 0, t: 0 },
      { y: 10, t: 900 },
      { y: 60, t: 950 },
      { y: 110, t: 1000 },
    ];
    expect(releaseVelocity(samples, 1000)).toBeCloseTo(1); // 100 px over 100 ms
  });

  it("is zero when the finger stopped before lifting", () => {
    expect(releaseVelocity([{ y: 0, t: 0 }, { y: 200, t: 100 }], 400)).toBe(0);
  });
});

describe("fling", () => {
  it("glides speed × time constant, starting at the release speed", () => {
    const f = fling(0, -1, -10_000, 0)!;
    expect(f.target).toBeCloseTo(-TIME_CONSTANT_MS);
    // Easing starts with slope 1/0.19: distance/duration × slope = release speed.
    expect((Math.abs(f.target) / f.durationMs) * (1 / 0.19)).toBeCloseTo(1);
  });

  it("stops at the ends", () => {
    expect(fling(-50, 2, -1000, 0)!.target).toBe(0);
    expect(fling(-950, -2, -1000, 0)!.target).toBe(-1000);
  });

  it("ignores slow releases and releases already at the end", () => {
    expect(fling(0, 0.05, -1000, 0)).toBeNull();
    expect(fling(0, 1, -1000, 0)).toBeNull();
  });
});

describe("rubberBand", () => {
  it("leaves in-range offsets alone and resists past the ends", () => {
    expect(rubberBand(-500, -1000, 0, 800)).toBe(-500);
    const over = rubberBand(200, -1000, 0, 800);
    expect(over).toBeGreaterThan(0);
    expect(over).toBeLessThan(200);
    expect(rubberBand(-1200, -1000, 0, 800)).toBeGreaterThan(-1200);
  });
});
