from functools import lru_cache

import urwid
import asyncio
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from environs import Env

import logging

logger = logging.getLogger("sp")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

file_handler = logging.FileHandler("logs/sp.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.propagate = False

from enum import StrEnum

class Command(StrEnum):
    NEXT = "n"
    PREVIOUS = "p"
    PAUSE = " "
    STOP = "s"
    LIKE = "l"


env = Env()
env.read_env()

def create_sp():
    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
    return Spotify(auth_manager=SpotifyOAuth(scope=scope, open_browser=False, show_dialog=True))

sp = create_sp()

class SpotifyUI:
    def __init__(self, loop):
        self._current_track: dict | None = None
        self._current_playlist: dict | None = None

        self.loop = loop
        self.playlist_stat = urwid.Text("Playlist: ")
        self.playlist_text = urwid.Text("Current playlist will be displayed here")
        self.playlist_block = urwid.Columns([
            ('pack', urwid.Padding(self.playlist_stat, align='left')),
            ('pack', urwid.Padding(self.playlist_text, align='left'))
        ])

        self.artists_stat = urwid.Text("Artists: ")
        self.artists_text = urwid.Text("Current artists will be displayed here")
        self.artists_block = urwid.Columns([
            ('pack', urwid.Padding(self.artists_stat, align='left')),
            ('pack', urwid.Padding(self.artists_text, align='left'))
        ])

        self.track_stat = urwid.Text("Track: ")
        self.track_text = urwid.Text("Current track will be displayed here")
        self.track_block = urwid.Columns([
            ('pack', urwid.Padding(self.track_stat, align='left')),
            ('pack', urwid.Padding(self.track_text, align='left'))
        ])

        self.status_stat = urwid.Text("Status: ")
        self.status_text = urwid.Text("Current status will be displayed here")
        self.status_block = urwid.Columns([
            ('pack', urwid.Padding(self.status_stat, align='left')),
            ('pack', urwid.Padding(self.status_text, align='left'))
        ])

        self.current_input = ""
        self.main_layout = urwid.Pile([
            self.playlist_block,
            self.artists_block,
            self.track_block,
            self.status_block,
            urwid.Divider(),
        ])

        self.frame = urwid.Frame(
            body=urwid.SolidFill(' '),
            footer=self.main_layout
        )

        self.loop_widget = urwid.MainLoop(self.frame, unhandled_input=self.handle_input, event_loop=urwid.AsyncioEventLoop(loop=loop))
        asyncio.ensure_future(self.update_track())

    @property
    def current_track(self) -> dict | None:
        current_playback = sp.current_playback()

        if (
                not current_playback
                or current_playback.get("currently_playing_type") != "track"
        ):
            self._current_track = None
        else:
            track_id = current_playback["item"]["id"]
            if not self._current_track or self._current_track.get("id") != track_id:
                self._current_track = self.get_track_info(track_id)

        return self._current_track

    @property
    def current_playlist(self) -> dict | None:
        current_playback = sp.current_playback()

        if (
                not current_playback
                or current_playback["context"].get('type') != 'playlist'
        ):
            self._current_playlist = None
        else:
            playlist_uri = current_playback["context"]["uri"]
            if not self._current_playlist or self._current_playlist.get("uri") != playlist_uri:
                self._current_playlist = self.get_playlist_info(playlist_uri)

        return self._current_playlist

    async def update_track(self):
        while True:
            track_info = await self.get_current_track_info()
            logger.info(f"Track info: {track_info}")
            self.track_text.set_text(track_info.get('track', 'No track'))
            self.artists_text.set_text(track_info.get('artists', 'No track'))
            self.playlist_text.set_text(track_info.get('playlist', 'No track'))
            await asyncio.sleep(5)

    @lru_cache(maxsize=100)
    def get_track_info(self, track_id: str) -> dict:
        track = sp.track(track_id)
        track_name = track['name']
        artists = ", ".join([artist['name'] for artist in track['artists']])
        track_info = {"id": track_id, "name": track_name, "artists": artists}
        return track_info

    @lru_cache(maxsize=10)
    def get_playlist_info(self, playlist_uri: str) -> str:
        playlist = sp.playlist(playlist_uri)
        return playlist

    async def get_current_track_info(self):
        state = {"track": "No Track", "artists": "No Artists", "playlist": "No playlist"}

        track_info = self.current_track
        if track_info:
            state.update({"track": track_info['name'], "artists": track_info['artists']})

        if playlist_info := self.current_playlist:
            state.update({"playlist": playlist_info["name"]})

        return state

    def handle_input(self, key):
        if len(key) == 1:
            self.status_text.set_text(f"{key} pressed")
            self.current_input += key

    def run(self):
        self.loop_widget.run()

def main():
    loop = asyncio.get_event_loop()
    app = SpotifyUI(loop)
    app.run()

if __name__ == "__main__":
    main()