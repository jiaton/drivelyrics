import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { TextField } from "../../../components/ui/TextField";
import type { SpotifyStatus } from "../types";
import { useI18n } from "../../../i18n";
import { rich } from "../../../i18n/rich";
import { signOut } from "../../auth/api/useMe";
import type { User } from "../../auth/types";
import { LanguageSwitch } from "../../landing/components/LanguageSwitch";

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li style={{ display: "flex", gap: "0.75rem", lineHeight: 1.55 }}>
      <span style={{ color: "var(--color-accent)", fontWeight: 600, minWidth: "1.2rem" }}>{n}.</span>
      <div style={{ flex: 1 }}>{children}</div>
    </li>
  );
}

function CopyBox({ value }: { value: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.4rem" }}>
      <code style={{ flex: 1, padding: "0.5rem 0.75rem", border: "1px solid var(--color-fg-dim)", borderRadius: 8, userSelect: "all", WebkitUserSelect: "all", overflowWrap: "anywhere" }}>
        {value}
      </code>
      <Button
        variant="secondary"
        style={{ padding: "0.5rem 0.9rem" }}
        onClick={() => navigator.clipboard?.writeText(value).then(() => setCopied(true))}
      >
        {copied ? t.app.spotify.copied : t.app.spotify.copy}
      </Button>
    </div>
  );
}

/**
 * Each person links their own Spotify Developer app: Spotify only lets an app in
 * development mode serve accounts its owner allow-lists by hand, so one shared app
 * can't take sign-ups. Best done on a computer or phone — not in the car.
 */
export function SpotifySetup({
  user,
  status,
  saveApp,
  removeApp,
  onDone,
}: {
  user: User;
  status: SpotifyStatus;
  saveApp: (clientId: string, clientSecret: string) => Promise<void>;
  removeApp: () => Promise<void>;
  onDone?: () => void;
}) {
  const { t } = useI18n();
  const ts = t.app.spotify;
  const [clientId, setClientId] = useState(status.client_id);
  const [secret, setSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const result = new URLSearchParams(window.location.search).get("spotify") ?? "";

  const save = () => {
    setSaving(true);
    setError(null);
    saveApp(clientId.trim(), secret.trim())
      .then(() => setSecret(""))
      // The server's message for a malformed value is English; show ours instead.
      .catch((err: Error) => setError(err.message.includes("32-character") ? ts.badFormat : err.message))
      .finally(() => setSaving(false));
  };

  return (
    <Page width={680}>
      {/* A new user lands here before anything else exists: the way out has to be here too. */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "1rem", flexWrap: "wrap", color: "var(--color-fg-dim)", fontSize: "0.9rem" }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          {t.app.settings.signedInAs} <span style={{ color: "var(--color-fg)" }}>{user.email}</span>
        </span>
        <LanguageSwitch />
        <Button
          variant="ghost"
          style={{ padding: "0.4rem 0.8rem", fontSize: "0.9rem" }}
          onClick={() => {
            if (window.confirm(t.app.settings.signOutConfirm)) signOut();
          }}
        >
          {t.app.settings.signOut}
        </Button>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>{ts.title}</h1>
        {onDone ? (
          <Button variant="ghost" onClick={onDone}>
            {ts.backToLyrics}
          </Button>
        ) : null}
      </div>
      {ts.results[result] ? <p style={{ margin: 0, color: "var(--color-error)" }}>{ts.results[result]}</p> : null}
      <p style={{ margin: 0, color: "var(--color-fg-dim)", lineHeight: 1.55 }}>{ts.intro}</p>

      <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "1rem" }}>
        <Step n={1}>
          {rich(ts.step1, {
            link: (
              <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noreferrer" style={{ color: "var(--color-fg)" }}>
                developer.spotify.com/dashboard
              </a>
            ),
          })}
        </Step>
        <Step n={2}>
          {rich(ts.step2)}
          <CopyBox value={status.redirect_uri} />
          {rich(ts.step2b)}
        </Step>
        <Step n={3}>{rich(ts.step3)}</Step>
      </ol>

      <TextField label={ts.clientId} value={clientId} onChange={(e) => setClientId(e.target.value)} autoComplete="off" spellCheck={false} />
      <TextField
        label={status.app_configured ? ts.clientSecretSaved : ts.clientSecret}
        value={secret}
        onChange={(e) => setSecret(e.target.value)}
        type="password"
        autoComplete="off"
        spellCheck={false}
      />
      {error ? <p style={{ margin: 0, color: "var(--color-error)" }}>{error}</p> : null}
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <Button onClick={save} disabled={saving || !clientId.trim() || !secret.trim()} variant={status.app_configured ? "secondary" : "primary"}>
          {status.app_configured ? ts.update : ts.save}
        </Button>
        {status.app_configured ? (
          <Button onClick={() => window.location.assign("/api/spotify/connect")} variant={status.connected ? "secondary" : "primary"}>
            {status.connected ? ts.reconnect : ts.connect}
          </Button>
        ) : null}
        {status.app_configured ? (
          <Button
            variant="ghost"
            onClick={() => {
              if (window.confirm(ts.removeConfirm)) removeApp().then(() => (setClientId(""), setSecret("")));
            }}
          >
            {ts.remove}
          </Button>
        ) : null}
      </div>
      {status.app_configured && !status.connected ? <p style={{ margin: 0, color: "var(--color-fg-dim)" }}>{rich(ts.step4)}</p> : null}
      {status.connected ? <p style={{ margin: 0, color: "var(--color-accent)" }}>{ts.connected}</p> : null}
    </Page>
  );
}
