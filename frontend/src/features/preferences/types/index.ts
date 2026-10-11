export type LyricsSource = "auto" | "netease" | "lrclib";

export interface Preferences {
  show_translation: boolean;
  show_album_art: boolean;
  keep_screen_awake: boolean;
  lyrics_source: LyricsSource;
  show_jyutping: boolean;
}

export type PreferencesPatch = Partial<Preferences>;
