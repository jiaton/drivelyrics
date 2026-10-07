import { useEffect } from "react";

/**
 * Best-effort screen-wake-lock. Tesla's in-car browser support for the Wake Lock API
 * is unverified (see AGENTS.md) — this fails silently on any unsupported browser or
 * denied request rather than surfacing an error, since "the screen might dim" is not
 * worth showing the driver an error state over.
 */
export function useWakeLock(enabled: boolean) {
  useEffect(() => {
    if (!enabled || !("wakeLock" in navigator)) return;

    let sentinel: WakeLockSentinel | null = null;
    let cancelled = false;

    const acquire = async () => {
      try {
        sentinel = await navigator.wakeLock.request("screen");
      } catch {
        // Denied, or document not visible yet — nothing actionable to do here.
      }
    };

    // Browsers release the wake lock automatically when the document is hidden;
    // re-acquire it when the car browser's tab becomes visible again.
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && !cancelled) void acquire();
    };

    void acquire();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      void sentinel?.release().catch(() => {});
    };
  }, [enabled]);
}
