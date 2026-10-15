import { useState } from "react";
import { Button } from "./Button";
import { useI18n } from "../../i18n";

/** A value to copy by hand (selectable) or with one tap. */
export function CopyBox({ value, multiline = false }: { value: string; multiline?: boolean }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: multiline ? "flex-start" : "center", marginTop: "0.4rem" }}>
      <code
        style={{
          flex: 1,
          padding: "0.5rem 0.75rem",
          border: "1px solid var(--color-fg-dim)",
          borderRadius: 8,
          userSelect: "all",
          WebkitUserSelect: "all",
          overflowWrap: "anywhere",
          whiteSpace: multiline ? "pre-wrap" : undefined,
          fontSize: multiline ? "0.85rem" : undefined,
        }}
      >
        {value}
      </code>
      <Button variant="secondary" style={{ padding: "0.5rem 0.9rem", flexShrink: 0 }} onClick={() => navigator.clipboard?.writeText(value).then(() => setCopied(true))}>
        {copied ? t.app.spotify.copied : t.app.spotify.copy}
      </Button>
    </div>
  );
}
