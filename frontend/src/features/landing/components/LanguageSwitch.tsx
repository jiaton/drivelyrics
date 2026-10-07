import { useI18n, type Lang } from "../../../i18n";

const OPTIONS: { value: Lang; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文" },
];

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switch" role="radiogroup" aria-label={t.language}>
      {OPTIONS.map((o) => (
        <button key={o.value} role="radio" aria-checked={lang === o.value} className={lang === o.value ? "on" : ""} onClick={() => setLang(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
