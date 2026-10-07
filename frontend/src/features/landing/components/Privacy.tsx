import { useI18n } from "../../../i18n";
import { Brand } from "./Brand";
import { LanguageSwitch } from "./LanguageSwitch";
import { SiteFooter } from "./SiteFooter";
import "./landing.css";

/** /privacy — public, linked from the footer and from Google's OAuth consent screen. */
export function Privacy() {
  const { t } = useI18n();
  return (
    <div className="site">
      <div className="glow glow-a" />
      <header className="nav">
        <Brand />
        <nav>
          <LanguageSwitch />
        </nav>
      </header>
      <main className="section narrow prose">
        <h1>{t.privacy.title}</h1>
        <p className="muted">{t.privacy.updated}</p>
        {t.privacy.sections.map((s) => (
          <section key={s.h}>
            <h2>{s.h}</h2>
            {s.p.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </section>
        ))}
        <p>
          <a href="/">← {t.privacy.back}</a>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
