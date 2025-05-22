import logging
from typing import Any

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from src.spotycli.config import AppSettings

logger = logging.getLogger("sp")


class SpotifyAdapter:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.sp = self._create_sp()

    def _create_sp(self) -> Spotify:
        scope = (
            "user-read-playback-state user-modify-playback-state "
            "user-read-currently-playing user-library-modify playlist-modify-private"
        )
        return Spotify(
            auth_manager=SpotifyOAuth(
                client_id=self.settings.spotipy_client_id,
                client_secret=self.settings.spotipy_client_secret,
                redirect_uri=self.settings.spotipy_redirect_uri,
                scope=scope,
                open_browser=False,
                show_dialog=True,
            ),
            retries=5,
            requests_timeout=10,  # seconds
            backoff_factor=0.5,   # seconds
        )

    def current_playback(self) -> dict[str, Any] | None:
        res = self.sp.current_playback()
        if res:
            # Reduce payload size by removing less used fields
            if res.get("item") and res["item"].get("album"):
                res["item"]["album"].pop("available_markets", None)
            if res.get("item"):
                res["item"].pop("available_markets", None)
            return res
        return None

    def next_track(self) -> None:
        self.sp.next_track()

    def previous_track(self) -> None:
        self.sp.previous_track()

    def pause_playback(self) -> None:
        self.sp.pause_playback()

    def start_playback(self) -> None:
        self.sp.start_playback()

    def seek_track(self, position: int) -> None:
        self.sp.seek_track(position)

    def add_to_playlist(self, playlist_id: str, track_id: str) -> None:
        self.sp.playlist_add_items(playlist_id, [track_id])

    def add_if_not_exists(self, playlist_id: str, track_id: str) -> None:
        playlist_tracks = self.sp.playlist_items(playlist_id)
        if track_id not in [item["track"]["id"] for item in playlist_tracks["items"] if item and item.get("track")]:
            self.add_to_playlist(playlist_id, track_id)

    def remove_from_playlist(self, playlist_id: str, track_id: str) -> None:
        self.sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

    def like_track(self, track_id: str) -> None:
        self.sp.current_user_saved_tracks_add([track_id])

    def get_playlist_count(self, playlist_id: str) -> int:
        return self.sp.playlist_items(playlist_id)["total"]

    def get_sp_artist(self, artist_id: str):
        return self.sp.artist(artist_id)

    def get_sp_playlist_tracks(self, playlist_id: str, limit: int = 100) -> list[str]:
        track_uris = []
        offset = 0
        while True:
            playlist_data = self.sp.playlist_items(playlist_id, offset=offset, limit=limit)
            tracks = playlist_data['items']
            if not tracks:
                break
            for track_item in tracks:
                if track_item and track_item.get('track') and track_item['track'].get('id'):
                    track_uris.append(track_item['track']['id'])
            offset += limit
        return track_uris

    def get_sp_playlist_info(self, playlist_id: str):
        return self.sp.playlist(playlist_id) 