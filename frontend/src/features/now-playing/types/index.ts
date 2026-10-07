export interface NowPlaying {
  is_playing: boolean;
  track_id: string | null;
  name: string | null;
  artist: string | null;
  album_art_url: string | null;
  duration_ms: number | null;
  progress_ms: number | null;
  fetched_at: number; // unix seconds, server clock — informational only, not used for scroll timing
}

/**
 * NowPlaying plus a client-side monotonic timestamp. `receivedAtPerf` is
 * `performance.now()` at the moment this browser received the SSE event — it lets the
 * scroll math measure "how long ago did I receive this" using only this device's own
 * clock, never comparing against the server's `fetched_at`. Comparing wall clocks
 * across a server and a car's system clock isn't something to rely on: either one
 * could be off by seconds, and `performance.now()` can't drift out of sync with itself.
 */
export interface ClientNowPlaying extends NowPlaying {
  receivedAtPerf: number;
}

export interface LyricLine {
  t: number; // ms offset into the track
  text: string;
}

export interface TrackRef {
  trackId: string;
  title: string;
  artist: string;
  durationMs: number | null;
}

export interface LyricsPayload {
  lines: LyricLine[];
  translation_lines: LyricLine[];
  source: string; // "netease" | "lrclib" | "" = nothing found
  song_id: string;
  manual: boolean;
}

export interface Candidate {
  source: string;
  song_id: string;
  name: string;
  artists: string[];
  album: string | null;
  duration_ms: number | null;
  score: number;
  selected: boolean;
}
