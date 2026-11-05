import { useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { TextField } from "../../../components/ui/TextField";
import { useI18n } from "../../../i18n";
import { api, ApiError } from "../../../lib/api";
import { fill } from "../../../i18n/rich";
import { pairInfo } from "../api/sessions";
import type { PairInfo } from "../types";
import { SignInOptions } from "./SignInOptions";
import type { Me } from "../types";

/** The phone side of pairing (/pair?code=…): reached by scanning the car's QR code. */
export function PairApprove({ me, onSignedIn }: { me: Me; onSignedIn: () => void }) {
  const { t } = useI18n();
  const [code, setCode] = useState(new URLSearchParams(window.location.search).get("code") ?? "");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const here = `/pair?code=${encodeURIComponent(code)}`;
  // Which device shows this code: looked up once the code is complete, so the owner can
  // tell their own screen from one someone else wants approved.
  const [info, setInfo] = useState<PairInfo | "unknown" | null>(null);
  const complete = code.replace(/\W/g, "").length >= 6;
  const signedIn = me.user !== null;
  useEffect(() => {
    setInfo(null);
    if (!signedIn || !complete) return;
    let live = true;
    pairInfo(code)
      .then((found) => live && setInfo(found))
      .catch((err) => {
        if (!live) return;
        setInfo("unknown");
        if (err instanceof ApiError && err.status === 429) {
          setState("error");
          setMessage(err.message);
        }
      });
    return () => {
      live = false;
    };
  }, [code, complete, signedIn]);

  if (!me.user) {
    return (
      <Page>
        <h1 style={{ margin: 0 }}>{t.pair.title}</h1>
        <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.5 }}>
          {t.pair.needSignIn}
        </p>
        <SignInOptions me={me} next={here} onSignedIn={onSignedIn} />
      </Page>
    );
  }

  const approve = () => {
    setState("busy");
    api("/api/auth/pair/approve", { method: "POST", json: { code } })
      .then(() => setState("done"))
      .catch((err: Error) => {
        setState("error");
        setMessage(err.message);
      });
  };

  return (
    <Page>
      <h1 style={{ margin: 0 }}>{t.pair.title}</h1>
      {state === "done" ? (
        <p style={{ margin: 0, fontSize: "1.2rem", lineHeight: 1.5 }}>{t.pair.done}</p>
      ) : (
        <>
          <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.5 }}>
            {t.pair.warning} <b style={{ color: "var(--color-fg)" }}>{me.user.email}</b> {t.pair.warningEnd}
          </p>
          <TextField label={t.pair.codeLabel} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoCapitalize="characters" />
          {info && info !== "unknown" ? (
            <div style={{ border: "1px solid rgba(255,255,255,0.18)", borderRadius: 10, padding: "0.9rem 1rem", lineHeight: 1.5 }}>
              <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem" }}>{t.pair.asking}</div>
              <div style={{ color: "var(--color-fg)", fontSize: "1.1rem" }}>{info.device || t.pair.unknownDevice}</div>
              <div style={{ color: "var(--color-fg-dim)", fontSize: "0.9rem" }}>
                {info.location || t.pair.unknownPlace} · {fill(t.pair.askedAt, { time: new Date(info.asked_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })}
              </div>
              <div style={{ color: "var(--color-fg-dim)", fontSize: "0.85rem", marginTop: "0.4rem" }}>{t.pair.notYours}</div>
            </div>
          ) : null}
          {info === "unknown" && state !== "error" ? <p style={{ margin: 0, color: "var(--color-error)" }}>{t.pair.expired}</p> : null}
          {state === "error" ? <p style={{ margin: 0, color: "var(--color-error)" }}>{message === "code not found or expired" ? t.pair.expired : message}</p> : null}
          <Button onClick={approve} disabled={state === "busy" || !info || info === "unknown"}>
            {t.pair.approve}
          </Button>
        </>
      )}
    </Page>
  );
}
