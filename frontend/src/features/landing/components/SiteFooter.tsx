import { useI18n } from "../../../i18n";

export function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <span>© {new Date().getFullYear()} {t.footer.rights}</span>
      <a href="/privacy">{t.footer.privacy}</a>
    </footer>
  );
}
