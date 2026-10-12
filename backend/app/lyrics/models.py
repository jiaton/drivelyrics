from sqlmodel import Field, SQLModel


class TrackMatch(SQLModel, table=True):
    """Which song in one provider a Spotify track's lyrics come from — one row per
    (track, source), so users preferring different sources share both caches. Shared by
    every user: one person's fix (manual=True) fixes it for all, and a manual row beats
    any automatic one whatever the reader's source preference (see service.get_lyrics).
    source_song_id "" means "looked in this source, found nothing" — still cached."""

    spotify_track_id: str = Field(primary_key=True)
    source: str = Field(primary_key=True)  # "netease" | "lrclib"
    title: str
    artist: str
    source_song_id: str = Field(default="")
    match_version: int  # see service.MATCH_VERSION; manual rows are never re-matched
    manual: bool = Field(default=False)
    chosen_by: int | None = Field(default=None, foreign_key="users.id")
    updated_at: float


class LyricsText(SQLModel, table=True):
    """LRC text per provider song, fetched once. Static, so never invalidated."""

    source: str = Field(primary_key=True)
    song_id: str = Field(primary_key=True)
    lrc_text: str  # "" = the provider has no synced lyrics for it
    tlyric_text: str = Field(default="")  # translation LRC, "" if none
    # The provider ships a romanization of these lyrics (NetEase `romalrc`) — for
    # Han-script lyrics that means Cantonese (see jyutping.py). None = fetched before
    # this was recorded; read again from the provider when it matters.
    romanized: bool | None = Field(default=None)
    fetched_at: float


class CantoneseVote(SQLModel, table=True):
    """One reader's word on whether a track is sung in Cantonese, overriding the guess
    (cantonese.is_cantonese) either way. Their own vote decides what they see; everyone
    else sees the majority, and a tie (or no votes) is left to the guess. So two camps
    re-marking a song can't flip it back and forth for others: each moves one vote."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    spotify_track_id: str = Field(primary_key=True)
    cantonese: bool
    updated_at: float


class UserTrackSource(SQLModel, table=True):
    """One reader's "show me this source for this track", set when they pick lyrics from
    a source other than the one they were shown without saying it was the wrong song —
    i.e. they just prefer that source here. Affects only them (order.reader_order)."""

    user_id: int = Field(primary_key=True, foreign_key="users.id")
    spotify_track_id: str = Field(primary_key=True)
    source: str
    updated_at: float
