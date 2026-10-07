import type { ReactNode } from "react";

/** Scrollable full-height page for the non-lyrics screens (sign-in, setup, pairing). */
export function Page({ children, width = 560 }: { children: ReactNode; width?: number }) {
  return (
    <div style={{ height: "100%", overflowY: "auto", WebkitOverflowScrolling: "touch" }}>
      <div style={{ maxWidth: width, margin: "0 auto", padding: "2.5rem 1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {children}
      </div>
    </div>
  );
}
