import type { InputHTMLAttributes } from "react";

export function TextField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", color: "var(--color-fg-dim)", fontSize: "0.9rem" }}>
      {label}
      <input
        {...props}
        style={{
          background: "transparent",
          color: "var(--color-fg)",
          border: "1px solid var(--color-fg-dim)",
          borderRadius: 8,
          padding: "0.6rem 0.75rem",
          fontSize: "1rem",
          fontFamily: "ui-monospace, monospace",
          userSelect: "text",
          WebkitUserSelect: "text",
          ...props.style,
        }}
      />
    </label>
  );
}
