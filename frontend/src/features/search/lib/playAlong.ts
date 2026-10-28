import type { ClientNowPlaying } from "../../now-playing/types";

/**
 * Play-along on the search screen: the reader drags (or taps) to the line being sung
 * and the lyrics follow from there on this device's clock. The anchor — which song,
 * where, and when (wall clock) — is kept on the device, so reopening the page carries on
 * where the song would be now. Device state like the UI language, not a preference.
 */
const KEY = "playalong";
/** Reopened this long after the last line's time: the song is over, start static. */
export const RESUME_GRACE_MS = 30_000;

export type Anchor = { song: string; positionMs: number; at: number }; // at: Date.now()

export function clockAt(positionMs: number, nowPerf: number): ClientNowPlaying {
  return {
    is_playing: true,
    track_id: null,
    name: null,
    artist: null,
    album_art_url: null,
    duration_ms: null,
    progress_ms: Math.max(0, Math.round(positionMs)),
    fetched_at: Date.now() / 1000,
    source: "feed",
    notice: null,
    receivedAtPerf: nowPerf,
  };
}

/** Where a saved anchor puts the song now, or null if it isn't this song or it's over. */
export function resumePosition(anchor: Anchor | null, song: string, lastLineMs: number, nowWall: number): number | null {
  if (!anchor || anchor.song !== song) return null;
  const position = anchor.positionMs + (nowWall - anchor.at);
  return position >= 0 && position <= lastLineMs + RESUME_GRACE_MS ? position : null;
}

export function loadAnchor(): Anchor | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Anchor) : null;
  } catch {
    return null;
  }
}

export function saveAnchor(anchor: Anchor): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(anchor));
  } catch {
    /* no storage: play-along still works, just isn't remembered */
  }
}

export function clearAnchor(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}
