import { useI18n } from "../../../i18n";

export function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <span>© {new Date().getFullYear()} {t.footer.rights}</span>
      <span style={{ display: "flex", gap: "1.25rem" }}>
        <a href="https://github.com/jiaton/drivelyrics" target="_blank" rel="noreferrer">{t.footer.source}</a>
        <a href="/privacy">{t.footer.privacy}</a>
      </span>
    </footer>
  );
}
