export interface TrackRow {
  title: string;
  artist: string;
  detail: string;
  by: string | null;
  at: number;
}

export interface Stats {
  db_bytes: number;
  tables: { name: string; rows: number }[];
  users: {
    id: number;
    email: string;
    role: string;
    created_at: number;
    last_seen_at: number | null;
    sessions: number;
    spotify_app: boolean;
    spotify_connected: boolean;
    lyrics_source: string;
    show_translation: boolean;
    screens_open: number;
  }[];
  pollers_running: number;
  screens_open: number;
  sources: { source: string; tracks_matched: number; tracks_not_found: number; corrections: number; marked_wrong: number }[];
  personal_source_pins: number;
  counters_since: number;
  counters: Record<string, number>;
  not_found: TrackRow[];
  recent_picks: TrackRow[];
}
