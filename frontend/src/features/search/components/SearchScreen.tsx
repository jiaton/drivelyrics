import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../../components/ui/Button";
import { LoadingSpinner } from "../../../components/ui/LoadingSpinner";
import { ApiError } from "../../../lib/api";
import { formatDuration } from "../../../lib/format";
import { navigate, useLocation } from "../../../lib/nav";
import { useI18n } from "../../../i18n";
import type { LyricsData } from "../../now-playing/api/useLyrics";
import { LyricsView } from "../../now-playing/components/LyricsView";
import { useWakeLock } from "../../now-playing/hooks/useWakeLock";
import { usePreferences } from "../../preferences/api/usePreferences";
import { fetchSong, searchSongs } from "../api/search";
import type { SearchHit } from "../types";
import "./SearchScreen.css";

const hitKey = (h: SearchHit) => `${h.source}:${h.song_id}`;
const searchUrl = (params: Record<string, string>) => `/search?${new URLSearchParams(params)}`;

/**
 * Look up any song's lyrics, playing or not. State lives in the URL (/search?q=…&song=
 * source:id), so the browser's back button steps through it. The now-playing screen is
 * unmounted while this is open, which closes its stream — the server stops polling
 * Spotify a minute later and starts again the moment "Exit search" goes back.
 */
export function SearchScreen() {
  const { t } = useI18n();
  const ts = t.app.search;
  const location = useLocation();
  const params = new URLSearchParams(location.split("?")[1] ?? "");
  const query = params.get("q") ?? "";
  const song = params.get("song") ?? "";

  const [input, setInput] = useState(query);
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [lyrics, setLyrics] = useState<LyricsData | null>(null);
  const [songError, setSongError] = useState<string | null>(null);
  const { preferences, updatePreferences } = usePreferences();

  useWakeLock(preferences.keep_screen_awake && !!lyrics);

  useEffect(() => setInput(query), [query]); // back/forward puts the field in step

  useEffect(() => {
    setResults(null);
    setSearchError(null);
    if (!query) return;
    let cancelled = false;
    searchSongs(query)
      .then((hits) => !cancelled && setResults(hits))
      .catch((err: Error) => !cancelled && setSearchError(err instanceof ApiError && err.status === 429 ? ts.tooFast : ts.failed));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    setLyrics(null);
    setSongError(null);
    const [source, songId] = song.split(":");
    if (!source || !songId) return;
    let cancelled = false;
    fetchSong(source, songId)
      .then((data) => !cancelled && setLyrics(data))
      .catch((err: Error) => !cancelled && setSongError(err instanceof ApiError && err.status === 422 ? ts.noSynced : ts.failed));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (q) navigate(searchUrl({ q }));
  };
  const exit = () => navigate("/");
  const label = (source: string) => t.app.sourceNames[source] ?? source;

  if (song) {
    const hit = results?.find((h) => hitKey(h) === song);
    return (
      <div className="search-screen">
        <header className="search-header">
          <button className="search-link" onClick={() => navigate(searchUrl({ q: query }))}>
            ‹ {ts.results}
          </button>
          <span className="search-title">
            {hit ? `${hit.name} — ${hit.artists.join(", ")} · ${label(hit.source)}` : ""}
          </span>
          {lyrics && lyrics.translationLines.length > 0 ? (
            <button className="search-chip" aria-pressed={preferences.show_translation} onClick={() => updatePreferences({ show_translation: !preferences.show_translation })}>
              {ts.translation}
            </button>
          ) : null}
          {lyrics?.cantonese ? (
            <button className="search-chip" aria-pressed={preferences.show_jyutping} onClick={() => updatePreferences({ show_jyutping: !preferences.show_jyutping })}>
              {ts.jyutping}
            </button>
          ) : null}
          <button className="search-link" onClick={exit}>
            {ts.exit}
          </button>
        </header>
        <div className="search-body">
          {songError ? (
            <p className="search-note error" style={{ padding: "1rem 1.75rem" }}>
              {songError}
            </p>
          ) : !lyrics ? (
            <LoadingSpinner />
          ) : (
            <LyricsView
              lines={lyrics.lines}
              translationLines={lyrics.translationLines}
              showTranslation={preferences.show_translation}
              romanizationLines={lyrics.romanizationLines}
              showJyutping={preferences.show_jyutping}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="search-screen">
      <header className="search-header">
        <form className="search-form" onSubmit={submit} role="search">
          <input
            className="search-input"
            type="search"
            enterKeyHint="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ts.placeholder}
            aria-label={ts.placeholder}
            maxLength={100}
            autoFocus={!query}
          />
          <Button type="submit" disabled={!input.trim()}>
            {ts.submit}
          </Button>
        </form>
        <button className="search-link" onClick={exit}>
          {ts.exit}
        </button>
      </header>
      <div className="search-body">
        <div className="search-results">
          {!query ? <p className="search-note">{ts.hint}</p> : null}
          {query && !results && !searchError ? <p className="search-note">{ts.searching}</p> : null}
          {searchError ? <p className="search-note error">{searchError}</p> : null}
          {results?.length === 0 ? <p className="search-note">{ts.nothingFound}</p> : null}
          {results?.map((h) => (
            <button key={hitKey(h)} className="search-hit" onClick={() => navigate(searchUrl({ q: query, song: hitKey(h) }))}>
              <span className="search-hit-main">
                <div>{h.name}</div>
                <div className="search-hit-sub">
                  {h.artists.join(", ")}
                  {h.album ? ` · ${h.album}` : ""}
                </div>
              </span>
              <span className="search-hit-side">
                <div>{formatDuration(h.duration_ms)}</div>
                <div>{label(h.source)}</div>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
