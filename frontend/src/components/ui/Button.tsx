import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, React.CSSProperties> = {
  primary: { background: "var(--color-fg)", color: "var(--color-bg)", border: "1px solid var(--color-fg)" },
  secondary: { background: "transparent", color: "var(--color-fg)", border: "1px solid var(--color-fg-dim)" },
  ghost: { background: "transparent", color: "var(--color-fg-dim)", border: "1px solid transparent" },
};

export function Button({ variant = "primary", style, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      style={{
        ...VARIANTS[variant],
        borderRadius: 999,
        padding: "0.7rem 1.4rem",
        fontSize: "1rem",
        fontFamily: "inherit",
        cursor: props.disabled ? "default" : "pointer",
        opacity: props.disabled ? 0.5 : 1,
        ...style,
      }}
    />
  );
}
