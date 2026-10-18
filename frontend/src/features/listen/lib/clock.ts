import type { ClientNowPlaying } from "../../now-playing/types";
import type { Recognized } from "../api/listenApi";

/** Re-listen this long after the recognised song should have ended: the next one has started. */
export const NEXT_SONG_SLACK_MS = 1500;

/**
 * The listen screen's "now playing", kept on this device: where the song was when the
 * recording started, counted forward with this device's monotonic clock (like a
 * Spotify snapshot, so LyricsView follows it unchanged).
 */
export function clockFrom(match: Recognized, recordedAt: number): ClientNowPlaying {
  return {
    is_playing: true,
    track_id: match.track_id ?? null,
    name: match.title ?? null,
    artist: match.artist ?? null,
    album_art_url: null,
    duration_ms: match.duration_ms ?? null,
    progress_ms: match.position_ms ?? 0,
    fetched_at: Date.now() / 1000,
    source: "feed",
    receivedAtPerf: recordedAt,
  };
}

export function positionAt(clock: ClientNowPlaying, now: number): number {
  return (clock.progress_ms ?? 0) + (now - clock.receivedAtPerf);
}

/** The song is at `positionMs` now (a nudge, or the user tapping the line being sung). */
export function setPosition(clock: ClientNowPlaying, positionMs: number, now: number): ClientNowPlaying {
  return { ...clock, progress_ms: Math.max(0, Math.round(positionMs)), receivedAtPerf: now };
}

/** Without a known duration: assume the song ends this long after its last lyric line. */
export const OUTRO_GUESS_MS = 20_000;

/** When to listen for the next song, as a performance.now() time. The duration comes
 *  from the recognition, else is guessed from the lyrics' last line; null = unknown. */
export function nextListenAt(clock: ClientNowPlaying, lastLineMs: number | null = null): number | null {
  const duration = clock.duration_ms ?? (lastLineMs !== null ? lastLineMs + OUTRO_GUESS_MS : null);
  if (!duration) return null;
  return clock.receivedAtPerf + Math.max(0, duration - (clock.progress_ms ?? 0)) + NEXT_SONG_SLACK_MS;
}
