import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Preferences, PreferencesPatch } from "../types";

const DEFAULTS: Preferences = { show_translation: false, show_album_art: true, keep_screen_awake: true, lyrics_source: "auto" };

/**
 * `preferences` is optimistic (the modal should feel instant); `saved` is the server's
 * row as last confirmed. Anything the *server* reads preferences for — which lyrics
 * source to try first — must key off `saved`, or a request can race ahead of the PUT
 * and come back computed from the old value.
 */
export function usePreferences() {
  const [preferences, setPreferences] = useState<Preferences>(DEFAULTS);
  const [saved, setSaved] = useState<Preferences | null>(null);
  const [error, setError] = useState<string | null>(null);

  const accept = useCallback((body: Preferences) => {
    setPreferences(body);
    setSaved(body);
  }, []);

  useEffect(() => {
    api<Preferences>("/api/preferences")
      .then(accept)
      .catch((err: Error) => {
        setError(err.message);
        setSaved(DEFAULTS); // the server falls back to the same defaults
      });
  }, [accept]);

  const updatePreferences = useCallback(
    (patch: PreferencesPatch) => {
      setPreferences((prev) => ({ ...prev, ...patch }));
      api<Preferences>("/api/preferences", { method: "PUT", json: patch })
        .then(accept) // reconcile with the server's authoritative row
        .catch((err: Error) => setError(err.message));
    },
    [accept],
  );

  return { preferences, saved, loading: saved === null, error, updatePreferences };
}
