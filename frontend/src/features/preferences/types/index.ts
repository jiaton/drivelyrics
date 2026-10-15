import type { Schema } from "../../../lib/schema";

export type Preferences = Schema<"PreferencesResponse">;
export type LyricsSource = Preferences["lyrics_source"];
// Not Schema<"PreferencesUpdate">: that allows explicit nulls, which the optimistic
// merge into Preferences mustn't see. Any subset of real values is a valid update.
export type PreferencesPatch = Partial<Preferences>;
