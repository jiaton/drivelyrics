export interface SearchHit {
  source: string;
  song_id: string;
  name: string;
  artists: string[];
  album: string | null;
  duration_ms: number | null;
}
