import { useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { useI18n } from "../../../i18n";
import { fill } from "../../../i18n/rich";
import { chooseCandidate, useCandidates } from "../api/useCandidates";
import type { LyricsData } from "../api/useLyrics";
import type { Candidate, TrackRef } from "../types";
import { formatDuration } from "../../../lib/format";
import { fetchSong } from "../../search/api/search";

/**
 * "Wrong lyrics?" — every plausible match from every source, best first. Tapping one
 * shows its lyrics first (a title alone often can't tell two versions apart); the pick
 * is made from there.
 * - A pick from the source being shown corrects that source's match, for everyone.
 * - A pick from the other source first asks whether the shown lyrics were the wrong song:
 *   yes → that source is skipped for this track for everyone; no → it's only this
 *   reader's preference for this track (people pick just to get NetEase's translation).
 */
export function LyricsPicker({
  track,
  shownSource,
  onChosen,
  onClose,
}: {
  track: TrackRef;
  shownSource: string; // "" when nothing was shown
  onChosen: (data: LyricsData) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const tp = t.app.picker;
  const { candidates, error } = useCandidates(track);
  const [busy, setBusy] = useState<string | null>(null);
  const [chooseError, setChooseError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Candidate | null>(null);
  const [previewing, setPreviewing] = useState<Candidate | null>(null);

  const submit = (c: Candidate, wrongSource?: string) => {
    setConfirming(null);
    setBusy(`${c.source}:${c.song_id}`);
    setChooseError(null);
    chooseCandidate(track, c, wrongSource)
      .then(onChosen)
      .catch((err: Error) => setChooseError(err.message))
      .finally(() => setBusy(null));
  };

  const choose = (c: Candidate) => {
    setPreviewing(null);
    if (shownSource && c.source !== shownSource) setConfirming(c);
    else submit(c);
  };

  const label = (source: string) => t.app.sourceNames[source] ?? source;
  const shownLabel = label(shownSource);

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-fg-dim)",
          borderRadius: 12,
          width: "min(720px, 94vw)",
          maxHeight: "86vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.25rem 1.5rem 0.5rem" }}>
          <div>
            <h2 style={{ color: "var(--color-fg)", fontSize: "1.1rem", margin: 0 }}>{tp.title}</h2>
            <div style={{ color: "var(--color-fg-dim)", fontSize: "0.9rem", marginTop: 4 }}>
              {track.title} — {track.artist} · {formatDuration(track.durationMs)}
            </div>
          </div>
          <button onClick={onClose} aria-label={tp.close} style={{ background: "none", border: "none", color: "var(--color-fg-dim)", fontSize: "1.5rem", cursor: "pointer" }}>
            ×
          </button>
        </div>

        {confirming ? (
          <div style={{ padding: "1rem 1.5rem 1.5rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <p style={{ margin: 0, color: "var(--color-fg)", lineHeight: 1.5 }}>
              {fill(tp.wrongQuestion, { source: shownLabel })}
            </p>
            <Button onClick={() => submit(confirming, shownSource)}>{fill(tp.wrongYes, { source: shownLabel })}</Button>
            <Button variant="secondary" onClick={() => submit(confirming)}>
              {fill(tp.wrongNo, { source: label(confirming.source) })}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(null)}>
              {tp.back}
            </Button>
          </div>
        ) : previewing ? (
          <Preview candidate={previewing} onUse={() => choose(previewing)} onBack={() => setPreviewing(null)} />
        ) : null}

        <div style={{ overflowY: "auto", padding: "0.5rem 1rem 1rem", touchAction: "pan-y", display: confirming || previewing ? "none" : undefined }}>
          {error || chooseError ? <p style={{ color: "var(--color-error)", padding: "0 0.5rem" }}>{error ?? chooseError}</p> : null}
          {candidates === null && !error ? <p style={{ color: "var(--color-fg-dim)", padding: "0 0.5rem" }}>{tp.searching}</p> : null}
          {candidates?.length === 0 ? <p style={{ color: "var(--color-fg-dim)", padding: "0 0.5rem" }}>{tp.nothingFound}</p> : null}
          {candidates?.map((c) => {
            const key = `${c.source}:${c.song_id}`;
            const off = c.duration_ms != null && track.durationMs != null ? Math.round((c.duration_ms - track.durationMs) / 1000) : null;
            return (
              <button
                key={key}
                onClick={() => setPreviewing(c)}
                disabled={busy !== null}
                style={{
                  display: "flex",
                  width: "100%",
                  textAlign: "left",
                  gap: "1rem",
                  alignItems: "center",
                  padding: "0.85rem 0.75rem",
                  background: c.selected ? "rgba(255,255,255,0.08)" : "transparent",
                  border: "none",
                  borderBottom: "1px solid rgba(255,255,255,0.08)",
                  color: "var(--color-fg)",
                  fontFamily: "inherit",
                  fontSize: "1rem",
                  cursor: "pointer",
                  opacity: busy !== null && busy !== key ? 0.5 : 1,
                }}
              >
                <span style={{ width: "1.2rem", color: "var(--color-accent)" }}>{c.selected ? "✓" : ""}</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</div>
                  <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.artists.join(", ")}
                    {c.album ? ` · ${c.album}` : ""}
                  </div>
                </span>
                <span style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem", textAlign: "right", flexShrink: 0 }}>
                  {formatDuration(c.duration_ms)}
                  {off ? <span style={{ color: Math.abs(off) > 3 ? "var(--color-error)" : undefined }}> ({off > 0 ? "+" : ""}{off}s)</span> : null}
                  <div>{busy === key ? tp.loading : label(c.source)}</div>
                </span>
              </button>
            );
          })}
        </div>
        <div style={{ padding: "0.75rem 1.5rem 1.25rem", display: previewing ? "none" : undefined, borderTop: "1px solid rgba(255,255,255,0.12)", color: "var(--color-fg-dim)", fontSize: "0.8rem" }}>
          {shownSource
            ? fill(tp.footerShown, { source: shownLabel })
            : tp.footerNone}
        </div>
      </div>
    </div>
  );
}

/** A candidate's lyrics, read before picking it. Fetched like a search result's (cached, and it touches no track's match). */
function Preview({ candidate, onUse, onBack }: { candidate: Candidate; onUse: () => void; onBack: () => void }) {
  const { t } = useI18n();
  const tp = t.app.picker;
  const [data, setData] = useState<LyricsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchSong(candidate.source, candidate.song_id)
      .then((d) => live && setData(d))
      .catch((err: Error) => live && setError(err.message === "that song has no synced lyrics" ? tp.noSynced : err.message));
    return () => {
      live = false;
    };
  }, [candidate, tp.noSynced]);

  const translations = new Map((data?.translationLines ?? []).map((line) => [line.t, line.text]));

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
      <div style={{ padding: "0.25rem 1.5rem 0.5rem", color: "var(--color-fg)" }}>
        <div style={{ fontWeight: 600 }}>{candidate.name}</div>
        <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem" }}>
          {candidate.artists.join(", ")}
          {candidate.album ? ` · ${candidate.album}` : ""} · {formatDuration(candidate.duration_ms)} · {t.app.sourceNames[candidate.source] ?? candidate.source}
        </div>
      </div>
      <div style={{ overflowY: "auto", padding: "0.5rem 1.5rem", touchAction: "pan-y", flex: 1, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
        {!data && !error ? <p style={{ color: "var(--color-fg-dim)" }}>{tp.loading}</p> : null}
        {data?.lines
          .filter((line) => line.text.trim())
          .map((line, i) => (
            <div key={i} style={{ padding: "0.3rem 0", lineHeight: 1.4 }}>
              <span style={{ color: "var(--color-fg-dim)", fontSize: "0.75rem", fontFamily: "ui-monospace, monospace", marginRight: "0.75rem" }}>
                {formatDuration(line.t)}
              </span>
              <span style={{ color: "var(--color-fg)" }}>{line.text}</span>
              {translations.get(line.t) ? <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem", marginLeft: "3.2rem" }}>{translations.get(line.t)}</div> : null}
            </div>
          ))}
      </div>
      <div style={{ display: "flex", gap: "0.75rem", padding: "0.75rem 1.5rem 1.25rem", borderTop: "1px solid rgba(255,255,255,0.12)" }}>
        <Button onClick={onUse} disabled={!data}>
          {tp.use}
        </Button>
        <Button variant="ghost" onClick={onBack}>
          {tp.back}
        </Button>
      </div>
    </div>
  );
}
