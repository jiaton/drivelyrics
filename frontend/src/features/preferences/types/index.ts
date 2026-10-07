export type LyricsSource = "auto" | "netease" | "lrclib";

export interface Preferences {
  show_translation: boolean;
  show_album_art: boolean;
  keep_screen_awake: boolean;
  lyrics_source: LyricsSource;
}

export type PreferencesPatch = Partial<Preferences>;
