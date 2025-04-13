import logging
from dataclasses import dataclass
from functools import lru_cache

from src.spotycli.mongo_adapter import get_data
from src.spotycli.sp_adapter import get_sp_artist, get_sp_playlist_tracks
from src.spotycli.tech_playlists import prep_playlists

logger = logging.getLogger("clouder")


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


def get_cur_playlist(cur_pl_uri: str):
    sp_pl_id = cur_pl_uri.split(":")[-1]
    cur_playlist = get_data("sp_playlists", {"playlist_id": sp_pl_id})
    if cur_playlist:
        return cur_playlist[0]


@lru_cache
def get_playlists(clouder_week: str) -> tuple[dict, dict]:
    week_playlists = get_data("sp_playlists", {"clouder_week": clouder_week})
    base_playlists = {
        playlist["clouder_pl_name"]: playlist["playlist_id"]
        for playlist in week_playlists
        if playlist["clouder_pl_type"] == "base"
    }
    cat_playlists = {
        playlist["clouder_pl_name"]: playlist["playlist_id"]
        for playlist in week_playlists
        if playlist["clouder_pl_type"] == "category"
    }
    return base_playlists, cat_playlists


@lru_cache
def get_clouder_week_info(clouder_week: str):
    fields = ["style_id", "style", "week", "year", "week_start", "week_end"]
    return get_data("clouder_weeks", {"id": clouder_week}, fields)[0]


@lru_cache
def get_artist(artist_id: str) -> Artist:
    sp_artist = get_sp_artist(artist_id)
    return Artist(
        name=sp_artist["name"],
        id=sp_artist["id"],
        popularity=sp_artist["popularity"],
        followers=sp_artist["followers"]["total"],
    )


@lru_cache
def get_playlist(playlist_uri: str) -> ClouderPlaylist | None:
    if not playlist_uri:
        return None

    clouder_playlist = get_cur_playlist(playlist_uri)
    if not clouder_playlist:
        return None

    clouder_week = clouder_playlist["clouder_week"]
    base_pl, cat_pl = get_playlists(clouder_week)

    tracks_uris = get_sp_playlist_tracks(clouder_playlist["playlist_id"])

    is_base_pl = clouder_playlist["playlist_id"] in base_pl.values()
    return ClouderPlaylist(
        name=clouder_playlist["playlist_name"],
        id=clouder_playlist["playlist_id"],
        count=0,
        tracks_uris=tracks_uris,
        is_base_pl=is_base_pl,
        clouder_week=clouder_week,
        clouder_pl_type=clouder_playlist["clouder_pl_type"],
        clouder_pl_name=clouder_playlist["clouder_pl_name"],
        cat_playlists=cat_pl,
        base_playlists=base_pl,
    )


def get_track_points(duration: int, points_cnt: int = 5) -> list[int]:
    return [int(duration * i / points_cnt) for i in range(points_cnt)]


def get_current_state(sp_track) -> PlayerState:
    artists_ids = [artist["id"] for artist in sp_track["item"]["artists"]]
    artists = [get_artist(artist_id) for artist_id in artists_ids]
    artists_repr = " | ".join(
        [f"{art.name} ({art.followers}:{art.popularity})" for art in artists]
    )
    album_repr = f"{sp_track['item']['album']['name']} ({sp_track['item']['album']['album_type']})"
    track_points = get_track_points(sp_track["item"]["duration_ms"])
    track_repr = f"{sp_track['item']['name']} ({sp_track['item']['popularity']})"

    sp_pl_uri = sp_track.get("context", {}).get("uri", "")

    cur_playlist = get_playlist(sp_pl_uri)
    cat_menu_repr = ""
    cat_menu = []
    clouder_info = {}
    if cur_playlist:
        cat_menu_repr = " | ".join(
            [f"{name.capitalize()}" for name in cur_playlist.cat_playlists.keys()]
        )
        cat_menu = {
            name[0]: (name, pl_id) for name, pl_id in cur_playlist.cat_playlists.items()
        }
        clouder_info = get_clouder_week_info(cur_playlist.clouder_week)
        prep_pl = prep_playlists[clouder_info["style"]]
        cur_playlist.prep_playlists = prep_pl

    def cast_ms_to_str(ms: int):
        minutes = str(ms // 1000 // 60).zfill(2)
        seconds = str(ms // 1000 % 60).zfill(2)
        return f"{minutes}:{seconds}"

    duration_ms = sp_track["item"]["duration_ms"]
    progress_ms = sp_track["progress_ms"]
    progress_repr = f"{cast_ms_to_str(progress_ms)}/{cast_ms_to_str(duration_ms)}"
    progress_percent = int(progress_ms / duration_ms * 100)
    return PlayerState(
        name=sp_track["item"]["name"],
        track_repr=track_repr,
        id=sp_track["item"]["id"],
        progress_percent=progress_percent,
        progress_repr=progress_repr,
        release_date=sp_track["item"]["album"]["release_date"],
        artists=artists,
        artists_repr=artists_repr,
        album_repr=album_repr,
        popularity=sp_track["item"]["popularity"],
        track_points=track_points,
        clouder_info=clouder_info,
        playlist=cur_playlist,
        cat_menu_repr=cat_menu_repr,
        cat_menu=cat_menu,
    )
