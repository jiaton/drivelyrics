import { api, ApiError } from "../../../lib/api";
import { toLyricsData, type LyricsData } from "../../now-playing/api/useLyrics";
import type { LyricsPayload } from "../../now-playing/types";
import type { SearchHit } from "../types";

// Per page load, so stepping back and forth through the search history (results → song
// → results) doesn't ask again — the server allows one search a second. A failed
// request isn't kept: asking again should retry.
const MAX_ENTRIES = 30;
const searches = new Map<string, Promise<SearchHit[]>>();
const songs = new Map<string, Promise<LyricsData>>();

function remember<T>(cache: Map<string, Promise<T>>, key: string, load: () => Promise<T>): Promise<T> {
  const hit = cache.get(key);
  if (hit) return hit;
  const promise = load();
  promise.catch(() => cache.delete(key));
  if (cache.size >= MAX_ENTRIES) cache.delete(cache.keys().next().value!);
  cache.set(key, promise);
  return promise;
}

export function searchSongs(query: string): Promise<SearchHit[]> {
  const get = () => api<{ results: SearchHit[] }>(`/api/lyrics/search?${new URLSearchParams({ q: query })}`);
  return remember(searches, query, async () => {
    try {
      return (await get()).results;
    } catch (err) {
      // Two searches within a second: wait out the limit once instead of failing.
      if (!(err instanceof ApiError && err.status === 429)) throw err;
      await new Promise((resolve) => setTimeout(resolve, 1100));
      return (await get()).results;
    }
  });
}

export function fetchSong(source: string, songId: string): Promise<LyricsData> {
  return remember(songs, `${source}:${songId}`, async () =>
    toLyricsData(await api<LyricsPayload>(`/api/lyrics/song?${new URLSearchParams({ source, song_id: songId })}`)),
  );
}
