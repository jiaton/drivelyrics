import { useEffect, useState } from "react";
import { useI18n } from "../../../i18n";
import { ApiError } from "../../../lib/api";
import { devSignIn, emailSignIn, githubSignInUrl, googleSignInUrl, sendEmailCode } from "../api/useMe";
import type { Me } from "../types";
import "./signin.css";

/**
 * Every way in, wherever someone has to sign in (the front page, a phone approving a
 * car or an app): Google, GitHub, a code sent to the email. Each shows only when the
 * server has it configured. `next` is where Google and GitHub come back to.
 */
export function SignInOptions({ me, next = "/", onSignedIn }: { me: Me; next?: string; onSignedIn: () => void }) {
  const { t } = useI18n();
  return (
    <div className="signin">
      {me.google_enabled || me.github_enabled ? (
        <div className="signin-providers">
          {me.google_enabled ? (
            <button className="signin-btn signin-primary" onClick={() => window.location.assign(googleSignInUrl(next))}>
              <GoogleMark /> {t.hero.google}
            </button>
          ) : null}
          {me.github_enabled ? (
            <button className="signin-btn" onClick={() => window.location.assign(githubSignInUrl(next))}>
              <GitHubMark /> {t.hero.github}
            </button>
          ) : null}
        </div>
      ) : null}
      {me.email_enabled ? <EmailCode showDivider={me.google_enabled || me.github_enabled} onSignedIn={onSignedIn} /> : null}
      {me.dev_login ? <DevSignIn onSignedIn={onSignedIn} /> : null}
    </div>
  );
}

function EmailCode({ showDivider, onSignedIn }: { showDivider: boolean; onSignedIn: () => void }) {
  const { t, lang } = useI18n();
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait(wait - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  const explain = (err: unknown) => {
    const status = err instanceof ApiError ? err.status : 0;
    setError(
      status === 400 ? t.signin.wrong : status === 429 ? t.signin.tooMany : status === 422 ? t.signin.invalid : t.signin.notSent,
    );
  };

  const send = async (to: string) => {
    setBusy(true);
    setError("");
    try {
      const started = await sendEmailCode(to, lang);
      setSentTo(to);
      setCode("");
      setWait(started.resend_after);
    } catch (err) {
      explain(err);
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (!sentTo) return;
    setBusy(true);
    setError("");
    try {
      await emailSignIn(sentTo, code);
      onSignedIn();
    } catch (err) {
      explain(err);
      setBusy(false);
    }
  };

  return (
    <div className="signin-email">
      {showDivider ? <div className="signin-or">{t.signin.or}</div> : null}
      {sentTo === null ? (
        <form
          className="signin-row"
          onSubmit={(e) => {
            e.preventDefault();
            send(email.trim());
          }}
        >
          <input
            type="email"
            autoComplete="email"
            aria-label={t.signin.email}
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button className="signin-btn" type="submit" disabled={busy || !email.includes("@")}>
            {t.signin.send}
          </button>
        </form>
      ) : (
        <>
          <p className="signin-note">
            {t.signin.sentTo} <b>{sentTo}</b>
          </p>
          <form
            className="signin-row"
            onSubmit={(e) => {
              e.preventDefault();
              verify();
            }}
          >
            <input
              className="signin-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              aria-label={t.signin.code}
              placeholder="000000"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              autoFocus
            />
            <button className="signin-btn signin-primary" type="submit" disabled={busy || code.length !== 6}>
              {t.signin.submit}
            </button>
          </form>
          <div className="signin-links">
            <button type="button" disabled={busy || wait > 0} onClick={() => send(sentTo)}>
              {wait > 0 ? t.signin.resendIn.replace("{s}", String(wait)) : t.signin.resend}
            </button>
            <button
              type="button"
              onClick={() => {
                setSentTo(null);
                setError("");
              }}
            >
              {t.signin.other}
            </button>
          </div>
        </>
      )}
      {error ? <p className="signin-error">{error}</p> : null}
    </div>
  );
}

function DevSignIn({ onSignedIn }: { onSignedIn: () => void }) {
  return (
    <form
      className="signin-row"
      onSubmit={(e) => {
        e.preventDefault();
        const email = new FormData(e.currentTarget).get("email") as string;
        devSignIn(email).then(onSignedIn);
      }}
    >
      <input name="email" placeholder="dev sign-in: you@example.com" />
      <button className="signin-btn" type="submit">Go</button>
    </form>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

function GitHubMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
