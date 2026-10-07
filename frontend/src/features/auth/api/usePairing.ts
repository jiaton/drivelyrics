import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { PairStart } from "../types";

const POLL_MS = 2000;

/**
 * The car side of device pairing: get a code + QR, poll until a signed-in phone
 * approves it, then the poll response itself carries this browser's session cookie.
 * A new code is fetched shortly before the old one expires, so a screen left on the
 * sign-in page always shows a working QR.
 */
export function usePairing(onSignedIn: () => void) {
  const [pairing, setPairing] = useState<PairStart | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | undefined;
    let renewTimer: number | undefined;

    const start = () => {
      window.clearTimeout(pollTimer);
      window.clearTimeout(renewTimer);
      api<PairStart>("/api/auth/pair/start", { method: "POST" })
        .then((p) => {
          if (cancelled) return;
          setPairing(p);
          setError(null);
          renewTimer = window.setTimeout(start, Math.max(30, p.expires_in - 30) * 1000);
          poll(p.poll_secret);
        })
        .catch((err: Error) => {
          if (cancelled) return;
          setError(err.message);
          renewTimer = window.setTimeout(start, 10_000);
        });
    };

    const poll = (secret: string) => {
      pollTimer = window.setTimeout(() => {
        api<{ status: string }>("/api/auth/pair/poll", { method: "POST", json: { poll_secret: secret } })
          .then(({ status }) => {
            if (cancelled) return;
            if (status === "approved") onSignedIn();
            else if (status === "expired") start();
            else poll(secret);
          })
          .catch(() => !cancelled && poll(secret)); // flaky car connection: keep trying
      }, POLL_MS);
    };

    start();
    return () => {
      cancelled = true;
      window.clearTimeout(pollTimer);
      window.clearTimeout(renewTimer);
    };
  }, [onSignedIn]);

  return { pairing, error };
}
