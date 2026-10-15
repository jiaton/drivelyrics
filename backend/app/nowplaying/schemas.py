from typing import Literal

from pydantic import BaseModel

Source = Literal["spotify", "feed"]


class SourcesResponse(BaseModel):
    selected: Source  # the user's choice
    effective: Source | None  # what screens get: the choice if available, else the other; None = neither set up
    spotify_connected: bool
    feed_enabled: bool  # has at least one feed token


class SourceUpdate(BaseModel):
    source: Source
