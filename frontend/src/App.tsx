import { useCallback, useEffect, useState } from "react";
import { NowPlayingScreen } from "./features/now-playing/components/NowPlayingScreen";
import { Landing } from "./features/landing/components/Landing";
import { Privacy } from "./features/landing/components/Privacy";
import { PairApprove } from "./features/auth/components/PairApprove";
import { useMe } from "./features/auth/api/useMe";
import { useSpotifyStatus } from "./features/spotify-setup/api/useSpotifyStatus";
import { SpotifySetup } from "./features/spotify-setup/components/SpotifySetup";
import { AdminStats } from "./features/admin/components/AdminStats";
import { LoadingSpinner } from "./components/ui/LoadingSpinner";
import { ErrorState } from "./components/ui/ErrorState";
import type { User } from "./features/auth/types";
import { useI18n } from "./i18n";

function SignedInApp({ user, lyricsSources }: { user: User; lyricsSources: string[] }) {
  const { t } = useI18n();
  const { status, error, refresh, saveApp, removeApp } = useSpotifyStatus();
  const [setupOpen, setSetupOpen] = useState(false);
  const openSetup = useCallback(() => setSetupOpen(true), []);

  // Back from Spotify's consent screen (?spotify=connected): drop the query string.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("spotify") === "connected") {
      window.history.replaceState(null, "", "/");
    }
  }, []);

  if (error) return <ErrorState message={t.app.backendDown} />;
  if (!status) return <LoadingSpinner />;
  if (!status.connected || setupOpen) {
    return <SpotifySetup user={user} status={status} saveApp={saveApp} removeApp={removeApp} onDone={status.connected ? () => setSetupOpen(false) : undefined} />;
  }
  return <NowPlayingScreen user={user} lyricsSources={lyricsSources} onSpotifyDisconnected={refresh} onOpenSpotifySetup={openSetup} />;
}

export default function App() {
  const { t } = useI18n();
  const { me, error, refresh } = useMe();
  // Stable: the pairing poller restarts whenever this changes.
  const onSignedIn = useCallback(() => {
    window.history.replaceState(null, "", window.location.pathname === "/pair" ? window.location.pathname + window.location.search : "/");
    refresh();
  }, [refresh]);

  let screen;
  if (window.location.pathname === "/privacy") screen = <Privacy />;
  else if (error) screen = <ErrorState message={t.app.backendDown} />;
  else if (!me) screen = <LoadingSpinner />;
  else if (window.location.pathname === "/pair") screen = <PairApprove me={me} onSignedIn={onSignedIn} />;
  else if (!me.user) screen = <Landing me={me} onSignedIn={onSignedIn} />;
  else if (window.location.pathname === "/admin" && me.user.role === "admin") screen = <AdminStats />;
  else screen = <SignedInApp user={me.user} lyricsSources={me.lyrics_sources} />;

  return <div style={{ height: "100vh" }}>{screen}</div>;
}
