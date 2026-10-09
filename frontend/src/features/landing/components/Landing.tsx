import { useI18n } from "../../../i18n";
import { devSignIn, googleSignInUrl } from "../../auth/api/useMe";
import { usePairing } from "../../auth/api/usePairing";
import type { Me } from "../../auth/types";
import { Brand } from "./Brand";
import { GitHubLink } from "./GitHubLink";
import { LanguageSwitch } from "./LanguageSwitch";
import { LyricsDemo } from "./LyricsDemo";
import { SiteFooter } from "./SiteFooter";
import "./landing.css";

function formatCode(code: string) {
  return `${code.slice(0, 3)} ${code.slice(3)}`;
}

/**
 * The signed-out front page — and the car's sign-in screen: the pairing QR sits in the
 * hero, so a car opening drivelyrics.com can be signed in from a phone without scrolling
 * or typing. (Hidden on phone-sized screens: a phone is the device that scans.)
 */
export function Landing({ me, onSignedIn }: { me: Me; onSignedIn: () => void }) {
  const { t } = useI18n();
  const { pairing } = usePairing(onSignedIn);
  const failed = new URLSearchParams(window.location.search).get("signin") === "failed";
  const signIn = () => window.location.assign(googleSignInUrl());

  return (
    <div className="site">
      <div className="glow glow-a" />
      <div className="glow glow-b" />

      <header className="nav">
        <Brand />
        <nav>
          <a href="#how" className="nav-link">{t.nav.howItWorks}</a>
          <LanguageSwitch />
          <GitHubLink />
          {me.google_enabled ? (
            <button className="btn btn-small" onClick={signIn}>{t.nav.signIn}</button>
          ) : null}
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">{t.hero.eyebrow}</span>
            <h1>{t.hero.title}</h1>
            <p className="lead">{t.hero.subtitle}</p>
            {failed ? <p className="error">{t.hero.signinFailed}</p> : null}
            <div className="hero-actions">
              {me.google_enabled ? (
                <button className="btn btn-primary" onClick={signIn}>
                  <GoogleMark /> {t.hero.google}
                </button>
              ) : null}
              <a className="btn btn-ghost" href="#how">{t.hero.learnMore}</a>
            </div>
            {me.google_enabled ? <p className="new-here">{t.hero.newHere}</p> : null}
            {me.dev_login ? <DevSignIn onSignedIn={onSignedIn} /> : null}

            <div className="pair-card">
              <div className="pair-qr" dangerouslySetInnerHTML={pairing ? { __html: pairing.qr_svg } : undefined} />
              <div>
                <div className="pair-title">{t.hero.pairTitle}</div>
                <p>{t.hero.pairBody}</p>
                <p className="pair-code-line">
                  {t.hero.pairOr} <span className="pair-code">{pairing ? formatCode(pairing.code) : "··· ···"}</span>
                </p>
              </div>
            </div>
          </div>
          <LyricsDemo />
        </section>

        <section id="how" className="section">
          <h2>{t.steps.title}</h2>
          <ol className="steps">
            {t.steps.items.map((s, i) => (
              <li key={i} className="card">
                <span className="step-n">{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="section">
          <div className="privacy-band">
            <h2>{t.privacyBand.title}</h2>
            <p className="lead">{t.privacyBand.lead}</p>
            <ul>
              {t.privacyBand.items.map((item, i) => (
                <li key={i}>
                  <span className="check" aria-hidden>✓</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </div>
                </li>
              ))}
            </ul>
            <a href="/privacy" className="privacy-more">{t.footer.privacy} →</a>
          </div>
        </section>

        <section className="section">
          <h2>{t.features.title}</h2>
          <div className="features">
            {t.features.items.map((f, i) => (
              <div key={i} className="card">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="section narrow">
          <h2>{t.faq.title}</h2>
          {t.faq.items.map((f, i) => (
            <details key={i} className="faq">
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </section>

        {me.google_enabled ? (
          <section className="section cta">
            <h2>{t.cta.title}</h2>
            <button className="btn btn-primary" onClick={signIn}>{t.cta.button}</button>
          </section>
        ) : null}
      </main>

      <SiteFooter />
    </div>
  );
}

function DevSignIn({ onSignedIn }: { onSignedIn: () => void }) {
  return (
    <form
      className="dev-signin"
      onSubmit={(e) => {
        e.preventDefault();
        const email = new FormData(e.currentTarget).get("email") as string;
        devSignIn(email).then(onSignedIn);
      }}
    >
      <input name="email" placeholder="dev sign-in: you@example.com" />
      <button className="btn btn-small" type="submit">Go</button>
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
