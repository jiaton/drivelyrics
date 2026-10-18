import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { TextField } from "../../../components/ui/TextField";
import { fill } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import { listenApi, type KeyStatus } from "../api/listenApi";

/** Each user brings their own AudD token (paid by them, like their own Spotify app). */
export function ListenKeySetup({ status, problem, onSaved }: { status: KeyStatus; problem: string | null; onSaved: (next: KeyStatus) => void }) {
  const { t } = useI18n();
  const tl = t.app.listen;
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    listenApi
      .saveKey(token.trim())
      .then((next) => {
        setToken("");
        onSaved(next);
      })
      .catch((err: Error) => setError(err.message));
  };

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
      <h2 style={{ margin: 0 }}>{tl.keyTitle}</h2>
      <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.55 }}>{tl.keyIntro}</p>
      <a href="https://dashboard.audd.io/" target="_blank" rel="noreferrer" style={{ color: "var(--color-accent)" }}>
        {tl.keyLink}
      </a>
      {problem ? <p style={{ margin: 0, color: "var(--color-error)" }}>{problem}</p> : null}
      {status.configured ? <p style={{ margin: 0 }}>{fill(tl.keySaved, { hint: status.hint })}</p> : null}
      <TextField label={tl.keyLabel} type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} />
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <Button onClick={save} disabled={token.trim().length < 16}>
          {tl.keySave}
        </Button>
        {status.configured ? (
          <Button variant="ghost" onClick={() => listenApi.removeKey().then(() => onSaved({ configured: false, hint: "" }))}>
            {tl.keyRemove}
          </Button>
        ) : null}
      </div>
      {error ? <p style={{ margin: 0, color: "var(--color-error)" }}>{error}</p> : null}
      <p style={{ margin: 0, color: "var(--color-fg-dim)", fontSize: "0.85rem", lineHeight: 1.5 }}>{tl.privacy}</p>
    </div>
  );
}
