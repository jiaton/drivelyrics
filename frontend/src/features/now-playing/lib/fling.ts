/**
 * Phone-style momentum for the lyrics drag, without a per-frame loop: on release we
 * work out where an exponentially decaying fling would stop, then hand the whole glide
 * to one CSS transition (compositor thread), the same mechanism as the line-to-line
 * glide. The easing below starts with slope 1/0.19, so the duration is chosen to make
 * the glide's starting speed equal the finger's release speed — no visible jolt.
 */

export type Sample = { y: number; t: number };

/** Only the last stretch of the drag counts: a finger that stopped before lifting flings nothing. */
export const VELOCITY_WINDOW_MS = 100;
/** Exponential decay time constant: total glide ≈ release speed × this. iOS's normal
 * deceleration is ≈ 500 ms; the owner asked for noticeably less glide than that. */
export const TIME_CONSTANT_MS = 200;
export const FLING_EASING = "cubic-bezier(0.19, 1, 0.22, 1)";
const EASING_START_SLOPE = 1 / 0.19;
/** Slower releases (px/ms) just stop where they are. */
const MIN_FLING_VELOCITY = 0.15;
const MIN_DURATION_MS = 150;
const MAX_DURATION_MS = 1500;

export const SETTLE_MS = 400;
export const SETTLE_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

/** px/ms over the samples within VELOCITY_WINDOW_MS of `now`. */
export function releaseVelocity(samples: Sample[], now: number): number {
  const recent = samples.filter((s) => now - s.t <= VELOCITY_WINDOW_MS);
  if (recent.length < 2) return 0;
  const first = recent[0];
  const last = recent[recent.length - 1];
  const dt = last.t - first.t;
  return dt > 0 ? (last.y - first.y) / dt : 0;
}

/** Where a release at `velocity` glides to (kept within [min, max]), or null for no fling. */
export function fling(offset: number, velocity: number, min: number, max: number): { target: number; durationMs: number } | null {
  if (Math.abs(velocity) < MIN_FLING_VELOCITY) return null;
  const target = clamp(offset + velocity * TIME_CONSTANT_MS, min, max);
  const distance = Math.abs(target - offset);
  if (distance < 1) return null;
  const durationMs = clamp((EASING_START_SLOPE * distance) / Math.abs(velocity), MIN_DURATION_MS, MAX_DURATION_MS);
  return { target, durationMs };
}

/** Dragging past either end moves less and less (iOS's rubber-band curve). */
export function rubberBand(offset: number, min: number, max: number, dimension: number): number {
  const resist = (x: number) => (1 - 1 / ((x * 0.55) / dimension + 1)) * dimension;
  if (offset > max) return max + resist(offset - max);
  if (offset < min) return min - resist(min - offset);
  return offset;
}
