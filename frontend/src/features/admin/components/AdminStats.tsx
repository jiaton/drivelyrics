import type { ReactNode } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { useStats } from "../api/useStats";
import type { TrackRow } from "../types";

const cell: React.CSSProperties = { padding: "0.4rem 0.75rem 0.4rem 0", textAlign: "left", verticalAlign: "top", whiteSpace: "nowrap" };
const dim: React.CSSProperties = { color: "var(--color-fg-dim)" };

function ago(ts: number | null) {
  if (!ts) return "—";
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <h2 style={{ margin: 0, fontSize: "1.1rem" }}>{title}</h2>
      <div style={{ overflowX: "auto" }}>{children}</div>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <table style={{ borderCollapse: "collapse", fontSize: "0.9rem" }}>
      <thead>
        <tr>{head.map((h) => <th key={h} style={{ ...cell, ...dim, fontWeight: 400 }}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            {r.map((c, j) => <td key={j} style={cell}>{c}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function trackRows(rows: TrackRow[], withBy: boolean) {
  return rows.map((r) => [r.title, <span style={dim}>{r.artist}</span>, r.detail, ...(withBy ? [r.by ?? "—"] : []), <span style={dim}>{ago(r.at)}</span>]);
}

/** Owner-only numbers: who uses it, what the lyrics lookups cost and miss. */
export function AdminStats() {
  const { stats, error, refresh } = useStats();
  const c = stats?.counters ?? {};
  const served = (c.cached ?? 0) + (c.searched ?? 0);
  const shown = Object.entries(c).filter(([k]) => k.startsWith("shown:"));
  const errors = Object.entries(c).filter(([k]) => k.startsWith("error:"));

  return (
    <Page width={980}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
        <h1 style={{ margin: 0 }}>Stats</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <Button variant="secondary" onClick={refresh}>Refresh</Button>
          <Button variant="ghost" onClick={() => window.location.assign("/")}>Back to lyrics</Button>
        </div>
      </div>
      {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
      {!stats ? null : (
        <>
          <div style={{ display: "flex", gap: "2.5rem", flexWrap: "wrap" }}>
            {[
              ["Users", stats.users.length],
              ["Online now", `${stats.pollers_running} (${stats.screens_open} screens)`],
              ["Database", `${(stats.db_bytes / 1024 / 1024).toFixed(2)} MB`],
              ["Cache hit rate", served ? `${Math.round(((c.cached ?? 0) / served) * 100)}% of ${served}` : "—"],
            ].map(([label, value]) => (
              <div key={label as string}>
                <div style={{ ...dim, fontSize: "0.85rem" }}>{label}</div>
                <div style={{ fontSize: "1.6rem" }}>{value}</div>
              </div>
            ))}
          </div>

          <Section title="Users">
            <Table
              head={["Email", "Role", "Joined", "Last seen", "Sessions", "Spotify", "Lyrics source", "Translation", "Screens open"]}
              rows={stats.users.map((u) => [
                u.email,
                u.role,
                ago(u.created_at),
                ago(u.last_seen_at),
                u.sessions,
                u.spotify_connected ? "connected" : u.spotify_app ? "app only" : "—",
                u.lyrics_source,
                u.show_translation ? "on" : "off",
                u.screens_open || "",
              ])}
            />
          </Section>

          <Section title={`Lyrics since restart (${ago(stats.counters_since)})`}>
            <Table
              head={["Lookups from cache", "Lookups that searched", "Shown by source", "Provider errors", "Picks"]}
              rows={[[
                c.cached ?? 0,
                c.searched ?? 0,
                shown.map(([k, v]) => `${k.slice(6)} ${v}`).join(" · ") || "—",
                errors.map(([k, v]) => `${k.slice(6)} ${v}`).join(" · ") || "none",
                c.picks ?? 0,
              ]]}
            />
          </Section>

          <Section title="Matches by source (all time)">
            <Table
              head={["Source", "Matched", "Not found", "Corrected by hand", "Marked wrong"]}
              rows={stats.sources.map((s) => [s.source, s.tracks_matched, s.tracks_not_found, s.corrections, s.marked_wrong])}
            />
            <div style={{ ...dim, fontSize: "0.85rem" }}>Personal source choices (only affect their owner): {stats.personal_source_pins}</div>
          </Section>

          <Section title="No lyrics found (newest first)">
            {stats.not_found.length ? <Table head={["Title", "Artist", "Sources looked in", "When"]} rows={trackRows(stats.not_found, false)} /> : <span style={dim}>None.</span>}
          </Section>

          <Section title="Hand-picked corrections (newest first)">
            {stats.recent_picks.length ? <Table head={["Title", "Artist", "Pick", "By", "When"]} rows={trackRows(stats.recent_picks, true)} /> : <span style={dim}>None.</span>}
          </Section>

          <Section title="Tables">
            <Table head={["Table", "Rows"]} rows={stats.tables.map((t) => [t.name, t.rows])} />
          </Section>
        </>
      )}
    </Page>
  );
}
