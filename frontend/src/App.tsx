import { useCallback, useEffect, useState } from "react";
import { NowPlayingScreen } from "./features/now-playing/components/NowPlayingScreen";
import { Landing } from "./features/landing/components/Landing";
import { Privacy } from "./features/landing/components/Privacy";
import { PairApprove } from "./features/auth/components/PairApprove";
import { useMe } from "./features/auth/api/useMe";
import { useSpotifyStatus } from "./features/spotify-setup/api/useSpotifyStatus";
import { useSources } from "./features/now-playing/api/useSources";
import { FeedSettingsPage } from "./features/feed/components/FeedSettingsPage";
import { SpotifySetup } from "./features/spotify-setup/components/SpotifySetup";
import { AdminStats } from "./features/admin/components/AdminStats";
import { SearchScreen } from "./features/search/components/SearchScreen";
import { ListenScreen } from "./features/listen/components/ListenScreen";
import { navigate, useLocation } from "./lib/nav";
import { LoadingSpinner } from "./components/ui/LoadingSpinner";
import { ErrorState } from "./components/ui/ErrorState";
import type { User } from "./features/auth/types";
import { useI18n } from "./i18n";

function SignedInApp({ user, lyricsSources }: { user: User; lyricsSources: string[] }) {
  const { t } = useI18n();
  const { status, error, refresh, saveApp, removeApp } = useSpotifyStatus();
  const { sources, error: sourcesError, refresh: refreshSources, select: selectSource } = useSources();
  const [setupOpen, setSetupOpen] = useState(false);
  const openSetup = useCallback(() => setSetupOpen(true), []);
  // The Spotify link died, or an app was removed: what screens can show may have changed.
  const refreshAll = useCallback(() => {
    refresh();
    refreshSources();
  }, [refresh, refreshSources]);
  const removeAppAndRefresh = useCallback(async () => {
    await removeApp();
    refreshSources();
  }, [removeApp, refreshSources]);

  // Back from Spotify's consent screen (?spotify=connected): drop the query string.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("spotify") === "connected") {
      window.history.replaceState(null, "", "/");
    }
  }, []);

  if (sourcesError && !sources) return <ErrorState message={t.app.backendDown} />;
  if (!sources) return <LoadingSpinner />;
  if (window.location.pathname === "/feed") {
    return <FeedSettingsPage sources={sources} onSourcesChanged={refreshSources} selectSource={selectSource} />;
  }
  // Spotify or the now-playing feed: either one is enough to show lyrics.
  if (sources.effective === null || setupOpen) {
    // Only the setup page needs the Spotify status; the lyrics screen doesn't wait for it.
    if (error) return <ErrorState message={t.app.backendDown} />;
    if (!status) return <LoadingSpinner />;
    return (
      <SpotifySetup
        user={user}
        status={status}
        saveApp={saveApp}
        removeApp={removeAppAndRefresh}
        onDone={sources.effective !== null ? () => setSetupOpen(false) : undefined}
        onUseFeed={() => navigate("/feed")}
      />
    );
  }
  return (
    <NowPlayingScreen
      user={user}
      lyricsSources={lyricsSources}
      sources={sources}
      selectSource={selectSource}
      onSpotifyDisconnected={refreshAll}
      onOpenSpotifySetup={openSetup}
    />
  );
}

export default function App() {
  const { t } = useI18n();
  const { me, error, refresh } = useMe();
  useLocation(); // re-render on in-app navigation (lib/nav)
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
  // Before the Spotify check: searching works without a linked Spotify app.
  else if (window.location.pathname === "/search") screen = <SearchScreen />;
  else if (window.location.pathname === "/listen") screen = <ListenScreen />;
  else screen = <SignedInApp user={me.user} lyricsSources={me.lyrics_sources} />;

  return <div style={{ height: "100vh" }}>{screen}</div>;
}
