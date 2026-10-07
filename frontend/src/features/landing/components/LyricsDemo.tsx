import { useEffect, useState } from "react";
import { useI18n } from "../../../i18n";

const STEP_MS = 2400;
const LINE_PX = 80; // keep in sync with .demo-line height in landing.css

/**
 * A miniature of the real lyrics screen: invented English lyrics (no real song's text
 * on a public page, and no translation line — owner's call) stepping line by line, the
 * current one lit.
 * One state change every 2.4s and a CSS transform — nothing per frame, so it's as cheap
 * on a car's browser as the real view. Stands still for prefers-reduced-motion.
 */
export function LyricsDemo() {
  const { t } = useI18n();
  const lines = t.demo.lines;
  const [active, setActive] = useState(1);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setActive((i) => (i + 1) % lines.length), STEP_MS);
    return () => window.clearInterval(id);
  }, [lines.length]);

  return (
    <div className="demo" aria-hidden>
      <div className="demo-bar">
        <span className="demo-dot" />
        <span className="demo-track">Night Drive — The Passengers</span>
      </div>
      <div className="demo-viewport">
        <div className="demo-track-lines" style={{ transform: `translateY(${-active * LINE_PX}px)` }}>
          {lines.map((line, i) => (
            <div key={i} className={`demo-line${i === active ? " active" : ""}`}>
              <div className="demo-original">{line}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
