import { useMemo, useState } from "react";
import { useNowPlayingStream } from "../api/useNowPlayingStream";
import { toLyricsData, useLyrics } from "../api/useLyrics";
import { api, ApiError } from "../../../lib/api";
import { feedApi } from "../../feed/api/feedApi";
import type { Sources, SourceName } from "../api/useSources";
import { navigate } from "../../../lib/nav";
import { useWakeLock } from "../hooks/useWakeLock";
import { LyricsView } from "./LyricsView";
import { LyricsPicker } from "./LyricsPicker";
import { LoadingSpinner } from "../../../components/ui/LoadingSpinner";
import { Button } from "../../../components/ui/Button";
import { usePreferences } from "../../preferences/api/usePreferences";
import { SettingsModal } from "../../preferences/components/SettingsModal";
import type { User } from "../../auth/types";
import type { LyricsPayload, TrackRef } from "../types";
import { useI18n } from "../../../i18n";
import "./NowPlayingScreen.css";

const headerButton: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "var(--color-fg-dim)",
  cursor: "pointer",
  flexShrink: 0,
  fontFamily: "inherit",
};

export function NowPlayingScreen({
  user,
  lyricsSources,
  sources,
  selectSource,
  onSpotifyDisconnected,
  onOpenSpotifySetup,
}: {
  user: User;
  lyricsSources: string[];
  sources: Sources;
  selectSource: (source: SourceName) => Promise<void>;
  onSpotifyDisconnected: () => void;
  onOpenSpotifySetup: () => void;
}) {
  const { t } = useI18n();
  const { nowPlaying, status, latestRef } = useNowPlayingStream(onSpotifyDisconnected);
  const trackId = nowPlaying?.track_id ?? null;
  // One object per track, so hooks keyed on it don't refire on every SSE tick.
  const track = useMemo<TrackRef | null>(
    () =>
      trackId && nowPlaying?.name && nowPlaying.artist
        ? { trackId, title: nowPlaying.name, artist: nowPlaying.artist, durationMs: nowPlaying.duration_ms }
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [trackId],
  );
  const { preferences, saved, updatePreferences } = usePreferences();
  // What decides the server's source order for this user (backend: source_order), as
  // the server last confirmed it — see usePreferences.
  const sourceKey = !saved ? "" : saved.lyrics_source === "auto" ? `auto:${saved.show_translation}` : saved.lyrics_source;
  const { lines, translationLines, romanizationLines, cantonese, source: shownSource, loading, error, replace } = useLyrics(saved ? track : null, sourceKey);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  // The reader's vote on whether this track is Cantonese (theirs to decide, one vote for others).
  const setCantonese = (value: boolean) => {
    if (!track) return;
    api<LyricsPayload>("/api/lyrics/cantonese", {
      method: "PUT",
      json: { track_id: track.trackId, title: track.title, artist: track.artist, duration_ms: track.durationMs, cantonese: value },
    })
      .then((body) => replace(track.trackId, toLyricsData(body)))
      .catch(() => undefined); // the toggle just stays as it was
  };

  // The feed only updates when asked: refresh after skipping tracks (debounced server-side).
  const [refreshNote, setRefreshNote] = useState<string | null>(null);
  const refreshFeed = (confirmOverBudget = false) => {
    feedApi
      .refresh(confirmOverBudget)
      .then(() => setRefreshNote(null))
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 409 && !confirmOverBudget) {
          if (window.confirm(t.app.refreshBudgetConfirm)) refreshFeed(true);
          return;
        }
        setRefreshNote(err instanceof ApiError && err.message === "hourly" ? t.app.refreshHourly : t.app.refreshTooSoon);
        window.setTimeout(() => setRefreshNote(null), 4000);
      });
  };

  useWakeLock(preferences.keep_screen_awake && !!nowPlaying?.is_playing);

  if (!nowPlaying) {
    return <LoadingSpinner />;
  }

  const showAlbumArt = preferences.show_album_art && !!nowPlaying.album_art_url;
  const isFeed = nowPlaying.source === "feed";
  const refreshButton = isFeed ? (
    <button onClick={() => refreshFeed()} aria-label={t.app.refresh} title={t.app.refresh} style={{ ...headerButton, display: "flex", padding: 4 }}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M20 12a8 8 0 1 1-2.34-5.66" />
        <path d="M20 4v5h-5" />
      </svg>
    </button>
  ) : null;

  return (
    <div className="now-playing-screen">
      {showAlbumArt ? (
        <div className="album-art-backdrop" style={{ backgroundImage: `url(${nowPlaying.album_art_url})` }} />
      ) : null}

      <div className="now-playing-content">
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            padding: "1rem 1.5rem",
            color: "var(--color-fg-dim)",
          }}
        >
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: status === "open" ? "var(--color-accent)" : "var(--color-error)",
              flexShrink: 0,
            }}
          />
          {showAlbumArt ? (
            <img src={nowPlaying.album_art_url!} alt="" width={28} height={28} style={{ borderRadius: 4, flexShrink: 0 }} />
          ) : null}
          {sources.spotify_connected && sources.feed_enabled ? (
            <span style={{ fontSize: "0.7rem", border: "1px solid var(--color-fg-dim)", borderRadius: 999, padding: "0.05rem 0.5rem", flexShrink: 0 }}>
              {t.app.sourceLabels[nowPlaying.source] ?? nowPlaying.source}
            </span>
          ) : null}
          <span style={{ fontSize: "0.9rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
            {refreshNote ?? (nowPlaying.track_id ? `${nowPlaying.name} — ${nowPlaying.artist ?? ""}` : "")}
          </span>
          {refreshButton}
          {track && lines.length > 0 ? (
            <button onClick={() => setPickerOpen(true)} style={{ ...headerButton, fontSize: "0.85rem" }}>
              {t.app.wrongLyrics}
            </button>
          ) : null}
          <button onClick={() => navigate("/search")} aria-label={t.app.openSearch} title={t.app.openSearch} style={{ ...headerButton, display: "flex", padding: 4 }}>
            {/* An SVG, not a glyph: the car browser's fonts may not have one. */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="M15.5 15.5 21 21" />
            </svg>
          </button>
          <button onClick={() => setSettingsOpen(true)} aria-label={t.app.openSettings} style={{ ...headerButton, fontSize: "1.2rem" }}>
            ⚙
          </button>
        </header>

        <div style={{ flex: 1, minHeight: 0 }}>
          {!nowPlaying.track_id ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", height: "100%", alignItems: "center", justifyContent: "center", color: "var(--color-fg-dim)", fontSize: "var(--font-size-inactive)" }}>
              {isFeed ? t.app.nothingPlayingFeed : t.app.nothingPlaying}
              <Button variant="secondary" onClick={() => navigate("/search")}>
                {t.app.openSearch}
              </Button>
            </div>
          ) : loading && lines.length === 0 ? (
            <LoadingSpinner />
          ) : error ? (
            <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center", color: "var(--color-error)" }}>
              {t.app.lyricsFailed}
            </div>
          ) : lines.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", height: "100%", alignItems: "center", justifyContent: "center", color: "var(--color-fg-dim)", fontSize: "var(--font-size-inactive)" }}>
              {t.app.noLyrics}
              <Button variant="secondary" onClick={() => setPickerOpen(true)}>
                {t.app.searchLyrics}
              </Button>
            </div>
          ) : (
            <LyricsView
              lines={lines}
              translationLines={translationLines}
              showTranslation={preferences.show_translation}
              romanizationLines={romanizationLines}
              showJyutping={preferences.show_jyutping}
              syncOffsetMs={preferences.sync_offset_ms}
              nowPlayingRef={latestRef}
            />
          )}
        </div>
      </div>

      {settingsOpen ? (
        <SettingsModal
          user={user}
          lyricsSources={lyricsSources}
          preferences={preferences}
          cantonese={track && lines.length > 0 ? { value: cantonese, onChange: setCantonese } : null}
          sources={sources}
          onSelectSource={(source) => selectSource(source).catch(() => undefined)}
          onChange={updatePreferences}
          onOpenSpotifySetup={onOpenSpotifySetup}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
      {pickerOpen && track ? (
        <LyricsPicker
          track={track}
          shownSource={lines.length > 0 ? shownSource : ""}
          onChosen={(data) => {
            replace(track.trackId, data);
            setPickerOpen(false);
          }}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
    </div>
  );
}
