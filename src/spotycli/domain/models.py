from dataclasses import dataclass


@dataclass
class Artist:
    name: str
    id: str
    popularity: int
    followers: int


@dataclass
class ClouderPlaylist:
    name: str
    id: str
    count: int
    tracks_uris: list[str]
    is_base_pl: bool
    clouder_week: str
    clouder_pl_type: str
    clouder_pl_name: str
    cat_playlists: dict[str, str]
    base_playlists: dict
    prep_playlists: dict | None = None


@dataclass
class PlayerState:
    name: str
    track_repr: str
    id: str
    progress_percent: int
    progress_repr: str
    release_date: str
    artists: list[Artist]
    artists_repr: str
    album_repr: str
    popularity: int
    track_points: list[int]
    clouder_info: dict[str, str]
    playlist: ClouderPlaylist | None
    cat_menu_repr: str
    cat_menu: dict[str, tuple[str, str]] 