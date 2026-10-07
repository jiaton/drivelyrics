export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", padding: "0.75rem 0", cursor: "pointer" }}>
      <span style={{ color: "var(--color-fg)", fontSize: "1rem" }}>{label}</span>
      <span
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        style={{
          position: "relative",
          width: 44,
          height: 26,
          borderRadius: 999,
          flexShrink: 0,
          background: checked ? "var(--color-accent)" : "var(--color-fg-dim)",
          transition: "background var(--transition-fast)",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 3,
            left: checked ? 21 : 3,
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "var(--color-active)",
            transition: "left var(--transition-fast)",
          }}
        />
      </span>
    </label>
  );
}
