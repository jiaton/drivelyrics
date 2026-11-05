import { useCallback, useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { useI18n } from "../../../i18n";
import { fill } from "../../../i18n/rich";
import { navigate } from "../../../lib/nav";
import { listSessions, signOutEverywhere, signOutSession } from "../api/sessions";
import type { SessionInfo } from "../types";

/** /devices: every browser signed in to this account; sign one out, or all of them. */
export function DevicesPage() {
  const { t, lang } = useI18n();
  const td = t.app.devices;
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listSessions()
      .then((body) => setSessions(body.sessions))
      .catch((err: Error) => setError(err.message));
  }, []);
  useEffect(load, [load]);

  const date = (seconds: number) =>
    new Date(seconds * 1000).toLocaleDateString(lang === "zh" ? "zh-CN" : "en", { year: "numeric", month: "short", day: "numeric" });

  return (
    <Page>
      <button onClick={() => navigate("/")} style={{ alignSelf: "flex-start", background: "none", border: "none", color: "var(--color-fg-dim)", fontSize: "1rem", padding: 0, cursor: "pointer", fontFamily: "inherit" }}>
        {td.back}
      </button>
      <h1 style={{ margin: 0 }}>{td.title}</h1>
      <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.5 }}>{td.intro}</p>
      {error ? <p style={{ margin: 0, color: "var(--color-error)" }}>{error}</p> : null}
      <div style={{ display: "flex", flexDirection: "column" }}>
        {sessions?.map((s) => (
          <div key={s.id} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "0.9rem 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "var(--color-fg)" }}>
                {s.device || td.unknown}
                {s.current ? <span style={{ color: "var(--color-accent)", fontSize: "0.85rem" }}> · {td.thisDevice}</span> : null}
              </div>
              <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem", marginTop: 2 }}>
                {fill(td.signedIn, { via: td.via[s.via] ?? s.via, date: date(s.created_at) })} · {fill(td.lastUsed, { date: date(s.last_seen_at) })}
              </div>
            </div>
            {s.current ? null : (
              <Button variant="secondary" onClick={() => signOutSession(s.id).then(load, (err: Error) => setError(err.message))}>
                {td.signOut}
              </Button>
            )}
          </div>
        ))}
      </div>
      {sessions ? (
        <Button
          variant="secondary"
          style={{ alignSelf: "flex-start", color: "var(--color-error)", borderColor: "var(--color-error)" }}
          onClick={() => {
            if (window.confirm(td.everywhereConfirm)) signOutEverywhere().catch((err: Error) => setError(err.message));
          }}
        >
          {td.everywhere}
        </Button>
      ) : null}
    </Page>
  );
}
