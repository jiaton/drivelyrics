import { useI18n } from "../../i18n";

export function LoadingSpinner() {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-label={t.app.loading}
      style={{
        display: "flex",
        height: "100%",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--color-fg-dim)",
        fontSize: "var(--font-size-inactive)",
      }}
    >
      …
    </div>
  );
}
