import { Button } from "../../../components/ui/Button";
import { Toggle } from "../../../components/ui/Toggle";
import { api } from "../../../lib/api";
import { signOut } from "../../auth/api/useMe";
import { useI18n } from "../../../i18n";
import { LanguageSwitch } from "../../landing/components/LanguageSwitch";
import type { User } from "../../auth/types";
import type { LyricsSource, Preferences, PreferencesPatch } from "../types";

const SOURCE_ORDER: LyricsSource[] = ["auto", "netease", "lrclib"];

export function SettingsModal({
  user,
  lyricsSources,
  preferences,
  onChange,
  onOpenSpotifySetup,
  onClose,
}: {
  user: User;
  lyricsSources: string[];
  preferences: Preferences;
  onChange: (patch: PreferencesPatch) => void;
  onOpenSpotifySetup: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const ts = t.app.settings;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-fg-dim)",
          borderRadius: 12,
          width: "min(420px, 90vw)",
          padding: "1.5rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <h2 style={{ color: "var(--color-fg)", fontSize: "1.1rem", margin: 0 }}>{ts.title}</h2>
          <button
            onClick={onClose}
            aria-label={t.app.closeSettings}
            style={{ background: "none", border: "none", color: "var(--color-fg-dim)", fontSize: "1.5rem", cursor: "pointer", lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        <Toggle
          label={ts.showTranslation}
          checked={preferences.show_translation}
          onChange={(next) => onChange({ show_translation: next })}
        />
        <Toggle
          label={ts.showAlbumArt}
          checked={preferences.show_album_art}
          onChange={(next) => onChange({ show_album_art: next })}
        />
        <Toggle
          label={ts.keepAwake}
          checked={preferences.keep_screen_awake}
          onChange={(next) => onChange({ keep_screen_awake: next })}
        />

        {/* Only a choice when this deployment has more than one source (NetEase is optional). */}
        {lyricsSources.length > 1 ? (
        <div style={{ padding: "0.75rem 0" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
            <span style={{ color: "var(--color-fg)", fontSize: "1rem" }}>{ts.lyricsSource}</span>
            <div role="radiogroup" aria-label={ts.lyricsSource} style={{ display: "flex", border: "1px solid var(--color-fg-dim)", borderRadius: 999, overflow: "hidden", flexShrink: 0 }}>
              {SOURCE_ORDER.map((value) => (
                <button
                  key={value}
                  role="radio"
                  aria-checked={preferences.lyrics_source === value}
                  onClick={() => onChange({ lyrics_source: value })}
                  style={{
                    background: preferences.lyrics_source === value ? "var(--color-fg)" : "transparent",
                    color: preferences.lyrics_source === value ? "var(--color-bg)" : "var(--color-fg)",
                    border: "none",
                    padding: "0.4rem 0.8rem",
                    fontFamily: "inherit",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                  }}
                >
                  {value === "auto" ? ts.sourceAuto : t.app.sourceNames[value]}
                </button>
              ))}
            </div>
          </div>
          <div style={{ color: "var(--color-fg-dim)", fontSize: "0.8rem", marginTop: "0.4rem", lineHeight: 1.4 }}>
            {ts.sourceHints[preferences.lyrics_source]}{ts.fixWins}
          </div>
        </div>
        ) : null}

        <div className="site-lang-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.75rem 0" }}>
          <span style={{ color: "var(--color-fg)", fontSize: "1rem" }}>{t.language}</span>
          <LanguageSwitch />
        </div>

        <div style={{ borderTop: "1px solid rgba(255,255,255,0.12)", marginTop: "0.75rem", paddingTop: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div style={{ color: "var(--color-fg-dim)", fontSize: "0.9rem", overflow: "hidden", textOverflow: "ellipsis" }}>
            {ts.signedInAs} <span style={{ color: "var(--color-fg)" }}>{user.email}</span>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <Button variant="secondary" onClick={onOpenSpotifySetup}>
              {ts.spotifyApp}
            </Button>
            {user.role === "admin" ? (
              <Button variant="secondary" onClick={() => window.location.assign("/admin")}>
                {ts.stats}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              onClick={() => {
                if (window.confirm(ts.signOutConfirm)) signOut();
              }}
            >
              {ts.signOut}
            </Button>
          </div>
          <button
            onClick={() => {
              if (window.confirm(ts.deleteConfirm)) {
                api("/api/account", { method: "DELETE" }).then(() => window.location.assign("/"));
              }
            }}
            style={{ alignSelf: "flex-start", background: "none", border: "none", padding: 0, color: "var(--color-error)", fontSize: "0.85rem", cursor: "pointer", fontFamily: "inherit" }}
          >
            {ts.deleteAccount}
          </button>
        </div>
      </div>
    </div>
  );
}
