import { useI18n } from "../../../i18n";
import { usePairing } from "../../auth/api/usePairing";
import { SignInOptions } from "../../auth/components/SignInOptions";
import type { Me } from "../../auth/types";
import { Brand } from "./Brand";
import { GitHubLink, HA_HACS_URL, HA_REPO_URL, SOURCE_URL } from "./GitHubLink";
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
  const canSignIn = me.google_enabled || me.github_enabled || me.email_enabled || me.dev_login;

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
          {canSignIn ? <a className="btn btn-small" href="#signin">{t.nav.signIn}</a> : null}
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">{t.hero.eyebrow}</span>
            <h1>{t.hero.title}</h1>
            <p className="lead">{t.hero.subtitle}</p>
            {failed ? <p className="error">{t.hero.signinFailed}</p> : null}
            <div className="hero-actions" id="signin">
              <SignInOptions me={me} onSignedIn={onSignedIn} />
            </div>
            {canSignIn ? <p className="new-here">{t.hero.newHere}</p> : null}

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
                    <a className="code-link" href={item.code ? `${SOURCE_URL}/blob/main/${item.code}` : SOURCE_URL} target="_blank" rel="noreferrer">
                      {t.privacyBand.code} →
                    </a>
                  </div>
                </li>
              ))}
            </ul>
            <a href="/privacy" className="privacy-more">{t.footer.privacy} →</a>
          </div>
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

        <section id="home-assistant" className="section">
          <div className="ha-band">
            <span className="eyebrow">{t.homeAssistant.eyebrow}</span>
            <h2>{t.homeAssistant.title}</h2>
            <p className="lead">{t.homeAssistant.lead}</p>
            <ul>
              {t.homeAssistant.points.map((point, i) => (
                <li key={i}>
                  <h3>{point.title}</h3>
                  <p>{point.body}</p>
                </li>
              ))}
            </ul>
            <div className="hero-actions">
              <a className="btn btn-primary" href={HA_HACS_URL} target="_blank" rel="noreferrer">{t.homeAssistant.install}</a>
              <a className="btn btn-ghost" href={HA_REPO_URL} target="_blank" rel="noreferrer">{t.homeAssistant.more}</a>
            </div>
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

        {canSignIn ? (
          <section className="section cta">
            <h2>{t.cta.title}</h2>
            <a className="btn btn-primary" href="#signin">{t.cta.button}</a>
          </section>
        ) : null}
      </main>

      <SiteFooter />
    </div>
  );
}
