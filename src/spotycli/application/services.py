import logging
from functools import lru_cache

from src.spotycli.domain.models import Artist, ClouderPlaylist, PlayerState
from src.spotycli.infrastructure.mongo_adapter import MongoAdapter
from src.spotycli.infrastructure.spotify_adapter import SpotifyAdapter

logger = logging.getLogger("application")

PREP_NAME = "prep"


class PlayerDataService:
    def __init__(self, mongo_adapter: MongoAdapter, spotify_adapter: SpotifyAdapter):
        self.mongo_adapter = mongo_adapter
        self.spotify_adapter = spotify_adapter

    def get_cur_playlist_data(self, cur_pl_uri: str):
        sp_pl_id = cur_pl_uri.split(":")[-1]
        cur_playlist_data = self.mongo_adapter.get_data(
            "sp_playlists", {"playlist_id": sp_pl_id}
        )
        if cur_playlist_data:
            return cur_playlist_data[0]
        return None

    @lru_cache
    def get_clouder_playlists_for_week(self, clouder_week: str) -> tuple[dict, dict]:
        week_playlists = self.mongo_adapter.get_data(
            "sp_playlists", {"clouder_week": clouder_week}
        )
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
    def get_clouder_week_metadata(self, clouder_week: str):
        fields = ["style_id", "style", "week", "year", "week_start", "week_end"]
        results = self.mongo_adapter.get_data(
            "clouder_weeks", {"id": clouder_week}, fields
        )
        if results:
            return results[0]
        return None

    @lru_cache
    def get_artist_details(self, artist_id: str) -> Artist:
        sp_artist = self.spotify_adapter.get_sp_artist(artist_id)
        return Artist(
            name=sp_artist["name"],
            id=sp_artist["id"],
            popularity=sp_artist["popularity"],
            followers=sp_artist["followers"]["total"],
        )

    @lru_cache
    def get_playlist_details(self, playlist_uri: str) -> ClouderPlaylist | None:
        if not playlist_uri:
            return None

        clouder_playlist_data = self.get_cur_playlist_data(playlist_uri)
        if not clouder_playlist_data:
            return None

        clouder_week = clouder_playlist_data["clouder_week"]
        base_pl, cat_pl = self.get_clouder_playlists_for_week(clouder_week)

        tracks_uris = self.spotify_adapter.get_playlist_tracks(
            clouder_playlist_data["playlist_id"]
        )

        is_base_pl = clouder_playlist_data["playlist_id"] in base_pl.values()
        return ClouderPlaylist(
            name=clouder_playlist_data["playlist_name"],
            id=clouder_playlist_data["playlist_id"],
            count=0,  # Count will be updated by PlayerApplicationService
            tracks_uris=tracks_uris,
            is_base_pl=is_base_pl,
            clouder_week=clouder_week,
            clouder_pl_type=clouder_playlist_data["clouder_pl_type"],
            clouder_pl_name=clouder_playlist_data["clouder_pl_name"],
            cat_playlists=cat_pl,
            base_playlists=base_pl,
        )

    def get_track_points(self, duration: int, points_cnt: int = 5) -> list[int]:
        return [int(duration * i / points_cnt) for i in range(points_cnt)]

    @lru_cache
    def get_style_prep_playlists(self, style: str) -> dict[str, str]:
        playlists = self.mongo_adapter.get_data(
            "sp_playlists", {"style": style, "clouder_pl_type": PREP_NAME}
        )
        if playlists:
            prep_playlists = {
                playlist["clouder_pl_name"]: playlist["playlist_id"]
                for playlist in playlists
            }
            return prep_playlists
        return {}

    def get_current_player_state_details(self, sp_track_data) -> PlayerState:
        artists_ids = [artist["id"] for artist in sp_track_data["item"]["artists"]]
        artists = [self.get_artist_details(artist_id) for artist_id in artists_ids]
        artists_repr = " | ".join(
            [f"{art.name} ({art.followers}:{art.popularity})" for art in artists]
        )
        album_repr = (
            f"{sp_track_data['item']['album']['name']} "
            f"({sp_track_data['item']['album']['album_type']})"
        )
        track_points = self.get_track_points(sp_track_data["item"]["duration_ms"])
        track_repr = (
            f"{sp_track_data['item']['name']} ({sp_track_data['item']['popularity']})"
        )

        sp_pl_uri = sp_track_data.get("context", {}).get("uri", "")

        cur_playlist = self.get_playlist_details(sp_pl_uri)
        cat_menu_repr = ""
        cat_menu = {}
        clouder_info = {}
        if cur_playlist:
            cat_menu_repr = " | ".join(
                [name.capitalize() for name in cur_playlist.cat_playlists.keys()]
            )
            cat_menu = {
                name[0]: (name, pl_id)
                for name, pl_id in cur_playlist.cat_playlists.items()
            }
            clouder_info = self.get_clouder_week_metadata(cur_playlist.clouder_week)
            if clouder_info and "style" in clouder_info:
                prep_pl = self.get_style_prep_playlists(clouder_info["style"])
                cur_playlist.prep_playlists = prep_pl

        def _cast_ms_to_str(ms: int) -> str:
            minutes = str(ms // 1000 // 60).zfill(2)
            seconds = str(ms // 1000 % 60).zfill(2)
            return f"{minutes}:{seconds}"

        duration_ms = sp_track_data["item"]["duration_ms"]
        progress_ms = sp_track_data["progress_ms"]
        progress_repr = f"{_cast_ms_to_str(progress_ms)}/{_cast_ms_to_str(duration_ms)}"
        progress_percent = (
            int(progress_ms / duration_ms * 100) if duration_ms > 0 else 0
        )

        return PlayerState(
            name=sp_track_data["item"]["name"],
            track_repr=track_repr,
            id=sp_track_data["item"]["id"],
            progress_percent=progress_percent,
            progress_repr=progress_repr,
            release_date=sp_track_data["item"]["album"]["release_date"],
            artists=artists,
            artists_repr=artists_repr,
            album_repr=album_repr,
            popularity=sp_track_data["item"]["popularity"],
            track_points=track_points,
            clouder_info=clouder_info,
            playlist=cur_playlist,
            cat_menu_repr=cat_menu_repr,
            cat_menu=cat_menu,
        )


class PlayerApplicationService:
    def __init__(self, spotify_adapter: SpotifyAdapter, player_data_service: PlayerDataService):
        self.spotify_adapter = spotify_adapter
        self.player_data_service = player_data_service

    def get_current_playback_state(self) -> PlayerState | None:
        current_playback_data = self.spotify_adapter.current_playback()
        if not current_playback_data:
            return None
        state = self.player_data_service.get_current_player_state_details(
            current_playback_data
        )
        self.update_playlist_count_in_state(state)
        return state

    def update_playlist_count_in_state(self, state: PlayerState | None) -> None:
        if state and state.playlist:
            state.playlist.count = self.spotify_adapter.get_playlist_count(
                state.playlist.id
            ) 