import { useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { Toggle } from "../../../components/ui/Toggle";
import { fill } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import { api } from "../../../lib/api";
import type { Schema } from "../../../lib/schema";
import { devSignIn, googleSignInUrl } from "../../auth/api/useMe";
import type { Me } from "../../auth/types";

type LinkInfo = Schema<"LinkInfo">;

/** /link?code=…: a receiver (the Home Assistant integration) asked to be linked to an
 * account; approving gives it its own feed token, which the user never has to copy. */
export function LinkApprove({ me, onSignedIn }: { me: Me; onSignedIn: () => void }) {
  const { t } = useI18n();
  const tl = t.link;
  const code = new URLSearchParams(window.location.search).get("code") ?? "";
  const [info, setInfo] = useState<LinkInfo | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "busy" | "approved" | "denied" | "gone" | "error">("loading");
  const [message, setMessage] = useState("");
  const [useFeed, setUseFeed] = useState(true);
  const signedIn = Boolean(me.user);

  useEffect(() => {
    if (!signedIn) return;
    api<LinkInfo>(`/api/feed/link?code=${encodeURIComponent(code)}`)
      .then((next) => {
        setInfo(next);
        setState("ready");
      })
      .catch(() => setState("gone"));
  }, [code, signedIn]);

  if (!me.user) {
    const here = `/link?code=${encodeURIComponent(code)}`;
    return (
      <Page>
        <h1 style={{ margin: 0 }}>{tl.title}</h1>
        <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.5 }}>{tl.needSignIn}</p>
        {me.google_enabled ? <Button onClick={() => window.location.assign(googleSignInUrl(here))}>{t.hero.google}</Button> : null}
        {me.dev_login ? (
          <Button variant="secondary" onClick={() => devSignIn(window.prompt("Dev email") ?? "").then(onSignedIn)}>
            Dev sign-in
          </Button>
        ) : null}
      </Page>
    );
  }

  const decide = async (approve: boolean) => {
    setState("busy");
    try {
      if (!approve) {
        await api("/api/feed/link/deny", { method: "POST", json: { code } });
        setState("denied");
        return;
      }
      await api("/api/feed/link/approve", { method: "POST", json: { code } });
      if (useFeed) await api("/api/now-playing/source", { method: "PUT", json: { source: "feed" } });
      setState("approved");
    } catch (err) {
      setState("error");
      setMessage((err as Error).message);
    }
  };

  const name = info?.client_name ?? "";
  return (
    <Page>
      <h1 style={{ margin: 0 }}>{name ? fill(tl.titleNamed, { name }) : tl.title}</h1>
      {state === "loading" ? <p style={{ margin: 0, color: "var(--color-fg-dim)" }}>…</p> : null}
      {state === "gone" ? <p style={{ margin: 0, lineHeight: 1.5 }}>{tl.expired}</p> : null}
      {state === "approved" ? <p style={{ margin: 0, fontSize: "1.2rem", lineHeight: 1.5 }}>{fill(tl.done, { name })}</p> : null}
      {state === "denied" ? <p style={{ margin: 0, lineHeight: 1.5 }}>{tl.deniedDone}</p> : null}
      {state === "ready" || state === "busy" || state === "error" ? (
        <>
          <p style={{ margin: 0, lineHeight: 1.55 }}>
            {fill(tl.intro, { name })} <b>{me.user.email}</b>
          </p>
          <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.55 }}>{tl.scope}</p>
          <p style={{ margin: 0 }}>
            {tl.codeCheck} <b style={{ fontFamily: "monospace", fontSize: "1.2rem", letterSpacing: "0.08em" }}>{info?.code}</b>
          </p>
          <Toggle label={tl.useFeed} checked={useFeed} onChange={setUseFeed} />
          {state === "error" ? <p style={{ margin: 0, color: "var(--color-error)" }}>{message === "code not found or expired" ? tl.expired : message}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <Button onClick={() => decide(true)} disabled={state === "busy"}>
              {tl.approve}
            </Button>
            <Button variant="ghost" onClick={() => decide(false)} disabled={state === "busy"}>
              {tl.deny}
            </Button>
          </div>
        </>
      ) : null}
    </Page>
  );
}
