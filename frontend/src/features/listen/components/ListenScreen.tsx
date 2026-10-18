import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { LoadingSpinner } from "../../../components/ui/LoadingSpinner";
import { ApiError } from "../../../lib/api";
import { navigate } from "../../../lib/nav";
import { fill } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import { useLyrics } from "../../now-playing/api/useLyrics";
import { LyricsView } from "../../now-playing/components/LyricsView";
import { useWakeLock } from "../../now-playing/hooks/useWakeLock";
import type { ClientNowPlaying, LyricLine, TrackRef } from "../../now-playing/types";
import { usePreferences } from "../../preferences/api/usePreferences";
import { candidatesOf, firstWithLyrics, listenApi, trackOf, type KeyStatus, type Recognized } from "../api/listenApi";
import { clockFrom, nextListenAt, positionAt, setPosition } from "../lib/clock";
import { MicRecorder } from "../lib/recorder";
import { ListenKeySetup } from "./ListenKeySetup";
import "../../search/components/SearchScreen.css";

const FIRST_CLIP_MS = 6000; // short is enough: 6 s clips matched 100% in tests (2026-10-17)
const LONGER_CLIP_MS = 10000; // once more, longer, before giving up
const NUDGE_MS = 500;

type View = "loading" | "setup" | "start" | "following" | "unsupported" | "denied";
type Activity = null | "listening" | "longer" | "recognizing";

/**
 * /listen: recognise the song playing in the room from the microphone and follow its
 * lyrics on this device's clock — karaoke without searching. Phones and tablets (a
 * car's browser has no microphone). The position comes from AudD (±0.5 s); tapping
 * the line being sung, or ±0.5 s, corrects it; the next song is recognised when this
 * one should end.
 */
export function ListenScreen() {
  const { t } = useI18n();
  const tl = t.app.listen;
  const [view, setView] = useState<View>("loading");
  const [key, setKey] = useState<KeyStatus | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [activity, setActivity] = useState<Activity>(null);
  const [note, setNote] = useState<string | null>(null);
  const [match, setMatch] = useState<Recognized | null>(null);
  const [chosen, setChosen] = useState(0); // which candidate's lyrics are shown
  const [picking, setPicking] = useState(false);
  // The last unrecognised recording, playable on this device only (never uploaded again):
  // lets the user hear whether the microphone caught the music at all.
  const [lastClip, setLastClip] = useState<string | null>(null);
  const clockRef = useRef<ClientNowPlaying | null>(null);
  const recorder = useRef(new MicRecorder());
  const nextTimer = useRef<number | undefined>(undefined);
  const busy = useRef(false);
  const { preferences, saved, updatePreferences } = usePreferences();

  useWakeLock(view === "following" && preferences.keep_screen_awake);

  useEffect(() => {
    listenApi
      .keyStatus()
      .then((status) => {
        setKey(status);
        setView(!MicRecorder.supported() ? "unsupported" : status.configured ? "start" : "setup");
      })
      .catch((err: Error) => setProblem(err.message));
    const mic = recorder.current;
    return () => {
      window.clearTimeout(nextTimer.current);
      mic.close();
    };
  }, []);

  const lastLineRef = useRef<number | null>(null); // for songs recognised without a duration
  const scheduleNext = useCallback(() => {
    window.clearTimeout(nextTimer.current);
    const at = clockRef.current ? nextListenAt(clockRef.current, lastLineRef.current) : null;
    if (at !== null) nextTimer.current = window.setTimeout(() => listenRef.current(true), Math.max(1000, at - performance.now()));
  }, []);

  const listen = useCallback(
    async (automatic = false) => {
      if (busy.current) return;
      busy.current = true;
      setNote(null);
      try {
        await recorder.current.open();
      } catch {
        busy.current = false;
        setView("denied");
        return;
      }
      try {
        for (const clipMs of [FIRST_CLIP_MS, LONGER_CLIP_MS]) {
          setActivity(clipMs === FIRST_CLIP_MS ? "listening" : "longer");
          const { blob, startedAt, filename } = await recorder.current.record(clipMs);
          setActivity("recognizing");
          const result = await listenApi.recognize(blob, filename, clipMs);
          if (!result.matched) {
            setLastClip((old) => {
              if (old) URL.revokeObjectURL(old);
              return URL.createObjectURL(blob);
            });
          }
          if (result.matched) {
            clockRef.current = clockFrom(result, startedAt);
            setActivity("recognizing");
            setChosen(await firstWithLyrics(candidatesOf(result), result.duration_ms));
            setMatch(result);
            setPicking(false);
            setView("following");
            scheduleNext();
            return;
          }
        }
        setNote(automatic ? tl.noNext : tl.noMatch);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 402 || err.status === 409)) {
          setProblem(err.status === 402 ? fill(tl.keyRejected, { detail: err.message.replace(/^AudD refused the key: /, "") }) : null);
          setView("setup");
        } else {
          setNote(err instanceof Error ? err.message : String(err));
        }
      } finally {
        recorder.current.close(); // not listening any more: the mic indicator goes off
        busy.current = false;
        setActivity(null);
      }
    },
    [scheduleNext, tl],
  );
  const listenRef = useRef(listen);
  listenRef.current = listen;

  const moveTo = (positionMs: number) => {
    if (!clockRef.current) return;
    clockRef.current = setPosition(clockRef.current, positionMs, performance.now());
    scheduleNext();
  };
  const nudge = (deltaMs: number) => clockRef.current && moveTo(positionAt(clockRef.current, performance.now()) + deltaMs);
  const lockLine = (line: LyricLine) => moveTo(line.t);

  const candidates = useMemo(() => (match ? candidatesOf(match) : []), [match]);
  const current = candidates[chosen] ?? candidates[0];
  const track = useMemo<TrackRef | null>(() => (current ? trackOf(current, match?.duration_ms) : null), [current, match]);
  const sourceKey = !saved ? "" : saved.lyrics_source === "auto" ? `auto:${saved.show_translation}` : saved.lyrics_source;
  const lyrics = useLyrics(saved ? track : null, sourceKey);
  const lastLine = lyrics.lines.length ? lyrics.lines[lyrics.lines.length - 1].t : null;
  useEffect(() => {
    lastLineRef.current = lastLine;
    if (!match?.duration_ms && lastLine !== null) scheduleNext(); // the lyrics give a guess
  }, [lastLine, match, scheduleNext]);

  const status = activity === "listening" ? tl.listening : activity === "longer" ? tl.longer : activity === "recognizing" ? tl.recognizing : note;
  const exit = (
    <button className="search-link" onClick={() => navigate("/")}>
      {tl.exit}
    </button>
  );

  if (problem && !key) return <p style={{ padding: "2rem", color: "var(--color-error)" }}>{problem}</p>;
  if (view === "loading") return <LoadingSpinner />;

  if (view === "setup" && key) {
    return (
      <div className="search-screen" style={{ overflowY: "auto" }}>
        <header className="search-header">
          {exit}
          <span className="search-title">{tl.title}</span>
        </header>
        <ListenKeySetup
          status={key}
          problem={problem}
          onSaved={(next) => {
            setKey(next);
            setProblem(null);
            if (next.configured) setView("start");
          }}
        />
      </div>
    );
  }

  if (view !== "following") {
    const message = view === "unsupported" ? tl.unsupported : view === "denied" ? tl.denied : null;
    return (
      <div className="search-screen">
        <header className="search-header">
          {exit}
          <span className="search-title">{tl.title}</span>
          {key?.configured ? (
            <button className="search-link" onClick={() => setView("setup")}>
              {tl.keyChange}
            </button>
          ) : null}
        </header>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1.25rem", padding: "1.5rem", textAlign: "center" }}>
          {message ? (
            <p style={{ maxWidth: 420, lineHeight: 1.55 }}>{message}</p>
          ) : (
            <>
              <button
                onClick={() => listen()}
                disabled={activity !== null}
                aria-label={tl.start}
                style={{
                  width: 160,
                  height: 160,
                  borderRadius: "50%",
                  border: "none",
                  background: activity ? "var(--color-accent)" : "var(--color-fg)",
                  color: "var(--color-bg)",
                  fontSize: "1.2rem",
                  fontFamily: "inherit",
                  cursor: "pointer",
                  animation: activity ? "listen-pulse 1.2s ease-in-out infinite" : undefined,
                }}
              >
                {activity ? status : tl.start}
              </button>
              <p style={{ maxWidth: 420, color: "var(--color-fg-dim)", lineHeight: 1.55, margin: 0 }}>{note ?? tl.hint}</p>
              {note && lastClip ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.4rem", color: "var(--color-fg-dim)", fontSize: "0.85rem" }}>
                  {tl.lastClip}
                  <audio controls src={lastClip} style={{ maxWidth: 320 }} />
                </div>
              ) : null}
              <p style={{ maxWidth: 420, color: "var(--color-fg-dim)", fontSize: "0.8rem", lineHeight: 1.5, margin: 0 }}>{tl.privacy}</p>
            </>
          )}
        </div>
        <style>{"@keyframes listen-pulse { 50% { opacity: 0.6; transform: scale(0.96); } }"}</style>
      </div>
    );
  }

  return (
    <div className="search-screen">
      <header className="search-header">
        {exit}
        <button className="search-title search-link" style={{ textAlign: "left" }} onClick={() => setPicking((v) => !v)}>
          {current?.title} — {current?.artist} ▾
          {match && !match.exact ? ` · ${tl.estimated}` : ""}
          {status ? ` · ${status}` : ""}
        </button>
        {lyrics.translationLines.length > 0 ? (
          <button className="search-chip" aria-pressed={preferences.show_translation} onClick={() => updatePreferences({ show_translation: !preferences.show_translation })}>
            {t.app.search.translation}
          </button>
        ) : null}
        {lyrics.cantonese ? (
          <button className="search-chip" aria-pressed={preferences.show_jyutping} onClick={() => updatePreferences({ show_jyutping: !preferences.show_jyutping })}>
            {t.app.search.jyutping}
          </button>
        ) : null}
        <button className="search-chip" onClick={() => nudge(-NUDGE_MS)} aria-label="-0.5 s">
          −0.5s
        </button>
        <button className="search-chip" onClick={() => nudge(NUDGE_MS)} aria-label="+0.5 s">
          +0.5s
        </button>
        <Button variant="secondary" style={{ padding: "0.4rem 0.9rem", fontSize: "0.85rem" }} onClick={() => listen()} disabled={activity !== null}>
          {tl.resync}
        </Button>
      </header>
      {picking || (!lyrics.loading && lyrics.lines.length === 0 && current) ? (
        <div style={{ padding: "0.25rem 1.5rem 0.75rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <span className="search-note" style={{ padding: 0 }}>
            {lyrics.lines.length === 0 && current ? `${fill(tl.recognizedAs, { title: current.title, artist: current.artist })}. ` : ""}
            {tl.notThisSong}
          </span>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {candidates.map((c, i) => (
              <button key={c.track_id} className="search-chip" aria-pressed={i === chosen} onClick={() => { setChosen(i); setPicking(false); }}>
                {c.title} — {c.artist}
              </button>
            ))}
            <button className="search-chip" onClick={() => navigate(`/search?${new URLSearchParams({ q: current?.title ?? "" })}`)}>
              {tl.searchLyrics}
            </button>
          </div>
        </div>
      ) : null}
      <div className="search-body">
        {lyrics.loading && lyrics.lines.length === 0 ? (
          <LoadingSpinner />
        ) : lyrics.lines.length === 0 ? (
          <p className="search-note" style={{ padding: "1rem 1.75rem" }}>
            {tl.noLyrics}
          </p>
        ) : (
          <LyricsView
            lines={lyrics.lines}
            translationLines={lyrics.translationLines}
            showTranslation={preferences.show_translation}
            romanizationLines={lyrics.romanizationLines}
            showJyutping={preferences.show_jyutping}
            nowPlayingRef={clockRef}
            onLineTap={lockLine}
          />
        )}
      </div>
      <p style={{ margin: 0, padding: "0.5rem 1.5rem 0.9rem", color: "var(--color-fg-dim)", fontSize: "0.8rem", textAlign: "center" }}>{tl.tapHint}</p>
    </div>
  );
}
