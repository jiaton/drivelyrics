import { useMemo, useState } from "react";
import { useNowPlayingStream } from "../api/useNowPlayingStream";
import { useLyrics } from "../api/useLyrics";
import { useWakeLock } from "../hooks/useWakeLock";
import { LyricsView } from "./LyricsView";
import { LyricsPicker } from "./LyricsPicker";
import { LoadingSpinner } from "../../../components/ui/LoadingSpinner";
import { Button } from "../../../components/ui/Button";
import { usePreferences } from "../../preferences/api/usePreferences";
import { SettingsModal } from "../../preferences/components/SettingsModal";
import type { User } from "../../auth/types";
import type { TrackRef } from "../types";
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
  onSpotifyDisconnected,
  onOpenSpotifySetup,
}: {
  user: User;
  lyricsSources: string[];
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
  const { lines, translationLines, source: shownSource, loading, error, replace } = useLyrics(saved ? track : null, sourceKey);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useWakeLock(preferences.keep_screen_awake && !!nowPlaying?.is_playing);

  if (!nowPlaying) {
    return <LoadingSpinner />;
  }

  const showAlbumArt = preferences.show_album_art && !!nowPlaying.album_art_url;

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
          <span style={{ fontSize: "0.9rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
            {nowPlaying.track_id ? `${nowPlaying.name} — ${nowPlaying.artist}` : ""}
          </span>
          {track && lines.length > 0 ? (
            <button onClick={() => setPickerOpen(true)} style={{ ...headerButton, fontSize: "0.85rem" }}>
              {t.app.wrongLyrics}
            </button>
          ) : null}
          <button onClick={() => setSettingsOpen(true)} aria-label={t.app.openSettings} style={{ ...headerButton, fontSize: "1.2rem" }}>
            ⚙
          </button>
        </header>

        <div style={{ flex: 1, minHeight: 0 }}>
          {!nowPlaying.track_id ? (
            <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center", color: "var(--color-fg-dim)", fontSize: "var(--font-size-inactive)" }}>
              {t.app.nothingPlaying}
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
