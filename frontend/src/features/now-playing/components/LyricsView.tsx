import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import type { ClientNowPlaying, LyricLine } from "../types";
import { computeActiveIndex } from "../lib/activeIndex";
import { FLING_EASING, SETTLE_EASING, SETTLE_MS, fling, releaseVelocity, rubberBand, type Sample } from "../lib/fling";
import "./LyricsView.css";

const TICK_MS = 200;
const MANUAL_RESET_MS = 5000;
const TAP_MOVE_THRESHOLD_PX = 6;

/**
 * Line-level sync, not per-frame: a setInterval tick (5/sec) picks the active line
 * and writes one `transform` to the track element; the CSS `transition` on that
 * property does the actual glide on the compositor thread. No rAF loop, no React
 * re-render per tick — this is what keeps it smooth on the car browser's weaker GPU.
 *
 * Manual scroll: dragging pauses auto-follow (position *and* the active-line
 * highlight both freeze where they were when the drag started — matches how most
 * lyric apps behave, and is simpler than trying to keep the highlight live while the
 * viewport is under the user's control). A tap (no meaningful movement) snaps back
 * immediately; an actual drag snaps back automatically 5s after the scroll comes to rest.
 * Releasing mid-swipe keeps gliding and slows down like a phone list (lib/fling.ts: one
 * CSS transition, still no per-frame JS); past the first or last line the drag resists
 * and springs back. Touching during a glide stops it where it is.
 */
export function LyricsView({
  lines,
  translationLines,
  showTranslation,
  nowPlayingRef,
}: {
  lines: LyricLine[];
  translationLines: LyricLine[];
  showTranslation: boolean;
  nowPlayingRef: React.RefObject<ClientNowPlaying | null>;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const lineElsRef = useRef<(HTMLDivElement | null)[]>([]);
  const activeIndexRef = useRef(-1);
  const currentOffsetRef = useRef(0); // last applied translateY, so a drag can start from it

  const isManualRef = useRef(false);
  const draggingRef = useRef(false);
  const dragMovedRef = useRef(false);
  const dragStartYRef = useRef(0);
  const dragStartOffsetRef = useRef(0);
  const samplesRef = useRef<Sample[]>([]);
  const glidingUntilRef = useRef(0); // performance.now() at which the current fling ends
  const resetTimerRef = useRef<number | null>(null);

  // Translations are matched to the original lines by timestamp, not by array index —
  // NetEase's tlyric cue count doesn't always match the original 1:1 (instrumental
  // sections etc.), but the timestamps line up for the lines that do have a translation.
  const translationByTime = useMemo(() => {
    const map = new Map<number, string>();
    for (const line of translationLines) map.set(line.t, line.text);
    return map;
  }, [translationLines]);

  useLayoutEffect(() => {
    activeIndexRef.current = -1;
    currentOffsetRef.current = 0;
    isManualRef.current = false;
    lineElsRef.current.forEach((el) => el?.classList.remove("active"));
    glidingUntilRef.current = 0;
    if (trackRef.current) {
      trackRef.current.style.transition = "";
      trackRef.current.style.transform = "translate3d(0, 0, 0)";
    }
  }, [lines]);

  useEffect(() => {
    const computeCurrentIndex = () => {
      const np = nowPlayingRef.current;
      if (!np) return -1;

      // performance.now() only — never compare against the server's `fetched_at` wall
      // clock. This device's own monotonic clock can't drift relative to itself, so
      // this is immune to the server and the car disagreeing about what time it is.
      const currentMs = np.is_playing
        ? (np.progress_ms ?? 0) + (performance.now() - np.receivedAtPerf)
        : np.progress_ms ?? 0;

      return computeActiveIndex(lines, currentMs);
    };

    const applyActiveIndex = (index: number, force = false) => {
      const prevIndex = activeIndexRef.current;
      if (prevIndex === index && !force) return;

      if (prevIndex >= 0) lineElsRef.current[prevIndex]?.classList.remove("active");
      if (index >= 0) lineElsRef.current[index]?.classList.add("active");
      activeIndexRef.current = index;

      const viewport = viewportRef.current;
      const track = trackRef.current;
      const target = index >= 0 ? lineElsRef.current[index] : null;
      if (viewport && track && target) {
        // .lyrics-track is CSS `top: 50%` (see LyricsView.css), which already puts its
        // untransformed top at the viewport's vertical center — so centering a line
        // only needs to cancel out that line's own offset within the track, not
        // subtract viewport.clientHeight/2 again.
        const offset = target.offsetTop + target.clientHeight / 2;
        currentOffsetRef.current = -offset;
        track.style.transform = `translate3d(0, ${-offset}px, 0)`;
      }
    };

    const clearResetTimer = () => {
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current);
        resetTimerRef.current = null;
      }
    };

    const resetToAuto = () => {
      clearResetTimer();
      isManualRef.current = false;
      if (trackRef.current) trackRef.current.style.transition = "";
      applyActiveIndex(computeCurrentIndex(), true);
    };

    const scheduleResetTimer = (afterMs = 0) => {
      clearResetTimer();
      resetTimerRef.current = window.setTimeout(resetToAuto, MANUAL_RESET_MS + afterMs);
    };

    /** Track offsets that center the first / last line. */
    const bounds = () => {
      const els = lineElsRef.current;
      const first = els[0];
      const last = els[lines.length - 1];
      if (!first || !last) return { min: currentOffsetRef.current, max: currentOffsetRef.current };
      return { min: -(last.offsetTop + last.clientHeight / 2), max: -(first.offsetTop + first.clientHeight / 2) };
    };

    const moveTo = (offset: number, transition: string) => {
      currentOffsetRef.current = offset;
      const track = trackRef.current;
      if (!track) return;
      track.style.transition = transition;
      track.style.transform = `translate3d(0, ${offset}px, 0)`;
    };

    const tick = () => {
      if (isManualRef.current || lines.length === 0) return;
      applyActiveIndex(computeCurrentIndex());
    };

    const onPointerDown = (e: PointerEvent) => {
      const track = trackRef.current;
      const wasGliding = performance.now() < glidingUntilRef.current;
      glidingUntilRef.current = 0;
      // Freeze wherever a glide (a fling or the line-to-line transition) has got to.
      if (track) {
        const shown = getComputedStyle(track).transform;
        if (shown && shown !== "none") currentOffsetRef.current = new DOMMatrixReadOnly(shown).m42;
        moveTo(currentOffsetRef.current, "none");
      }
      draggingRef.current = true;
      // A tap that stops a glide is a scroll gesture, not "back to the current line".
      dragMovedRef.current = wasGliding;
      dragStartYRef.current = e.clientY;
      dragStartOffsetRef.current = currentOffsetRef.current;
      samplesRef.current = [{ y: e.clientY, t: e.timeStamp }];
      isManualRef.current = true;
      clearResetTimer();
      (e.target as Element).setPointerCapture?.(e.pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!draggingRef.current) return;
      const delta = e.clientY - dragStartYRef.current;
      if (Math.abs(delta) > TAP_MOVE_THRESHOLD_PX) dragMovedRef.current = true;
      samplesRef.current.push({ y: e.clientY, t: e.timeStamp });
      if (samplesRef.current.length > 20) samplesRef.current.shift();
      const { min, max } = bounds();
      const height = viewportRef.current?.clientHeight ?? 800;
      moveTo(rubberBand(dragStartOffsetRef.current + delta, min, max, height), "none");
    };

    const endDrag = (e: PointerEvent) => {
      if (!draggingRef.current) return;
      draggingRef.current = false;

      if (!dragMovedRef.current) {
        resetToAuto(); // tap — snap back immediately
        return;
      }
      const { min, max } = bounds();
      const offset = currentOffsetRef.current;
      let glideMs = 0;
      if (offset > max || offset < min) {
        moveTo(offset > max ? max : min, `transform ${SETTLE_MS}ms ${SETTLE_EASING}`); // spring back
        glideMs = SETTLE_MS;
      } else {
        const glide = fling(offset, releaseVelocity(samplesRef.current, e.timeStamp), min, max);
        if (glide) {
          moveTo(glide.target, `transform ${glide.durationMs}ms ${FLING_EASING}`);
          glideMs = glide.durationMs;
        }
      }
      glidingUntilRef.current = glideMs ? performance.now() + glideMs : 0;
      scheduleResetTimer(glideMs); // real drag — 5s after it comes to rest, back to the current line
    };

    const viewport = viewportRef.current;
    viewport?.addEventListener("pointerdown", onPointerDown);
    viewport?.addEventListener("pointermove", onPointerMove);
    viewport?.addEventListener("pointerup", endDrag);
    viewport?.addEventListener("pointercancel", endDrag);

    tick();
    const id = window.setInterval(tick, TICK_MS);
    return () => {
      window.clearInterval(id);
      clearResetTimer();
      viewport?.removeEventListener("pointerdown", onPointerDown);
      viewport?.removeEventListener("pointermove", onPointerMove);
      viewport?.removeEventListener("pointerup", endDrag);
      viewport?.removeEventListener("pointercancel", endDrag);
    };
  }, [lines, nowPlayingRef]);

  if (lines.length === 0) {
    return (
      <div className="lyrics-viewport">
        <div className="lyrics-line active" style={{ position: "absolute", top: "50%", left: 0, right: 0, transform: "translateY(-50%)" }}>
          No synced lyrics found for this track
        </div>
      </div>
    );
  }

  return (
    <div className="lyrics-viewport" ref={viewportRef}>
      <div className="lyrics-track" ref={trackRef}>
        {lines.map((line, i) => {
          const translation = showTranslation ? translationByTime.get(line.t) : undefined;
          return (
            <div
              key={line.t + "-" + i}
              className="lyrics-line"
              ref={(el) => {
                lineElsRef.current[i] = el;
              }}
            >
              <div className="lyrics-line-text">{line.text || " "}</div>
              {translation ? <div className="lyrics-line-translation">{translation}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
