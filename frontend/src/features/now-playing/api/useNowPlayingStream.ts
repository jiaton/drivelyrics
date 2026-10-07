import { useEffect, useRef, useState } from "react";
import type { ClientNowPlaying, NowPlaying } from "../types";

type StreamStatus = "connecting" | "open" | "error";

/**
 * Server state via SSE, not TanStack Query — the backend runs one Spotify poller per
 * user and pushes the latest snapshot to each of their open screens, so there is no per-client
 * request/response to cache; a query-library wrapper here would just be a thin shell
 * around EventSource for no real benefit. EventSource also already retries dropped
 * connections on its own, which matters on a car's cellular link.
 */
export function useNowPlayingStream(onDisconnected: () => void) {
  const [nowPlaying, setNowPlaying] = useState<ClientNowPlaying | null>(null);
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const latestRef = useRef<ClientNowPlaying | null>(null);

  useEffect(() => {
    const source = new EventSource("/api/spotify/now-playing/stream");

    source.addEventListener("open", () => setStatus("open"));
    let reloadTimer: number | undefined;
    source.addEventListener("error", () => {
      setStatus("error");
      // EventSource retries dropped connections itself, but gives up for good on a
      // non-200 answer (signed out elsewhere → 401, backend restarting → 502). A
      // reload after a pause re-runs the whole app: sign-in screen, or back to lyrics.
      if (source.readyState === EventSource.CLOSED) {
        window.clearTimeout(reloadTimer);
        reloadTimer = window.setTimeout(() => window.location.reload(), 10_000);
      }
    });
    // The server dropped the Spotify link (access revoked, app secret changed): stop
    // reconnecting and let the app show the Spotify setup screen.
    source.addEventListener("spotify-disconnected", () => {
      source.close();
      onDisconnected();
    });
    source.addEventListener("now-playing", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as NowPlaying;
      const withClientClock: ClientNowPlaying = { ...data, receivedAtPerf: performance.now() };
      latestRef.current = withClientClock;
      setNowPlaying(withClientClock);
    });

    return () => {
      window.clearTimeout(reloadTimer);
      source.close();
    };
  }, [onDisconnected]);

  return { nowPlaying, status, latestRef };
}
