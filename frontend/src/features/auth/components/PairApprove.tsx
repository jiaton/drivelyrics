import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { TextField } from "../../../components/ui/TextField";
import { useI18n } from "../../../i18n";
import { api } from "../../../lib/api";
import { devSignIn, googleSignInUrl } from "../api/useMe";
import type { Me } from "../types";

/** The phone side of pairing (/pair?code=…): reached by scanning the car's QR code. */
export function PairApprove({ me, onSignedIn }: { me: Me; onSignedIn: () => void }) {
  const { t } = useI18n();
  const [code, setCode] = useState(new URLSearchParams(window.location.search).get("code") ?? "");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const here = `/pair?code=${encodeURIComponent(code)}`;

  if (!me.user) {
    return (
      <Page>
        <h1 style={{ margin: 0 }}>{t.pair.title}</h1>
        <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.5 }}>
          {t.pair.needSignIn}
        </p>
        {me.google_enabled ? <Button onClick={() => window.location.assign(googleSignInUrl(here))}>{t.hero.google}</Button> : null}
        {me.dev_login ? (
          <Button variant="secondary" onClick={() => devSignIn(window.prompt("Dev email") ?? "").then(onSignedIn)}>
            Dev sign-in
          </Button>
        ) : null}
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
          {state === "error" ? <p style={{ margin: 0, color: "var(--color-error)" }}>{message === "code not found or expired" ? t.pair.expired : message}</p> : null}
          <Button onClick={approve} disabled={state === "busy" || code.replace(/\W/g, "").length < 6}>
            {t.pair.approve}
          </Button>
        </>
      )}
    </Page>
  );
}
