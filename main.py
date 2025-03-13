import asyncio
import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import urwid
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from src.spotycli.clouder_adapter import PlayerState, get_current_state
from src.spotycli.config import settings
from src.spotycli.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("main")

if settings.env == "dev":
    from dotenv import load_dotenv

    load_dotenv()


class PlayerCommand(StrEnum):
    NEXT = ">"
    PREVIOUS = "<"
    MOVE_10s = "."
    BACK_10s = ","
    STOP = " "
    LIKE = "!"


def create_sp() -> Spotify:
    scope = (
        "user-read-playback-state user-modify-playback-state "
        "user-read-currently-playing user-library-modify playlist-modify-private"
    )
    return Spotify(
        auth_manager=SpotifyOAuth(scope=scope, open_browser=False, show_dialog=True)
    )


class SpotifyService:
    def __init__(self) -> None:
        self.sp = create_sp()

    def current_playback(self) -> dict[str, Any] | None:
        res = self.sp.current_playback()
        if res:
            res["item"]["album"].pop("available_markets", None)
            res["item"].pop("available_markets", None)
            return res

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
        if track_id not in [item["track"]["id"] for item in playlist_tracks["items"]]:
            self.add_to_playlist(playlist_id, track_id)

    def remove_from_playlist(self, playlist_id: str, track_id: str) -> None:
        self.sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

    def like_track(self, track_id: str) -> None:
        self.sp.current_user_saved_tracks_add([track_id])

    def get_playlist_count(self, playlist_id: str) -> int:
        return self.sp.playlist_items(playlist_id)["total"]


class SpotifyController:
    def __init__(self, service: SpotifyService) -> None:
        self.service = service
        self.state: PlayerState | None = None
        self.status_message: str = ""

    async def update_state_loop(self, update_ui_callback: Callable[[], None]) -> None:
        while True:
            await asyncio.sleep(1)
            await self.update_state(update_ui_callback)

    async def update_state(self, update_ui_callback: Callable[[], None]) -> None:
        current_playback = self.service.current_playback()
        if not current_playback:
            self.state = None
            update_ui_callback()
            return

        # if self.state and self.state.id == current_playback["item"]["id"]:
        #     return

        self.state = get_current_state(current_playback)
        update_ui_callback()

    def update_playlist_count(self) -> None:
        if self.state and self.state.playlist:
            self.state.playlist.count = self.service.get_playlist_count(
                self.state.playlist.id
            )

    def handle_next_track(self) -> None:
        self.status_message = "Next track"
        if (
            self.state
            and self.state.playlist.is_base_pl
            and self.state.playlist.clouder_pl_type != "trash"
        ):
            self.service.add_to_playlist(
                self.state.playlist.base_playlists["trash"], self.state.id
            )
            self.service.remove_from_playlist(self.state.playlist.id, self.state.id)
        self.update_playlist_count()
        self.service.next_track()

    def handle_stop(self) -> None:
        cur_state = self.service.current_playback()
        if cur_state:
            if cur_state.get("is_playing"):
                self.status_message = "Stop track"
                self.service.pause_playback()
            else:
                self.status_message = "Resume track"
                self.service.start_playback()

    def handle_points_menu(self, point: int) -> None:
        self.status_message = f"Move to {point} point"
        new_position = self.state.track_points[point - 1]
        self.service.seek_track(new_position)

    def handle_cat_menu(self, key: str, amplified: bool = False) -> None:
        pl_name, pl_id = self.state.cat_menu[key]
        self.service.add_if_not_exists(pl_id, self.state.id)
        status_msg = f"'{self.state.name}' Moved to {pl_name.capitalize()}"
        if self.state.playlist and not self.state.playlist.is_base_pl:
            self.service.remove_from_playlist(self.state.playlist.id, self.state.id)
        if amplified:
            clouder_pl = self.state.playlist
            if clouder_pl:
                prep_pl_id = clouder_pl.prep_playlists[pl_name]
                self.service.add_if_not_exists(prep_pl_id, self.state.id)
                status_msg += " (amplified)"
        self.handle_next_track()
        self.status_message = status_msg

    def handle_like_track(self) -> None:
        msg = f"'{self.state.name}' Like track"
        if self.state and self.state.id:
            clouder_pl = self.state.playlist
            if clouder_pl and not clouder_pl.is_base_pl:
                cat_name = clouder_pl.clouder_pl_name
                prep_pl_id = clouder_pl.prep_playlists[cat_name]
                self.service.add_if_not_exists(prep_pl_id, self.state.id)
                msg = f"'{self.state.name}' Like track (amplified)"
            else:
                self.service.like_track(self.state.id)
        self.status_message = msg

    def handle_base_menu(self, command: PlayerCommand) -> None:
        if command == PlayerCommand.NEXT:
            self.handle_next_track()
        elif command == PlayerCommand.PREVIOUS:
            self.status_message = "Previous track"
            try:
                self.service.previous_track()
            except Exception:
                self.handle_points_menu(1)

        elif command == PlayerCommand.MOVE_10s:
            self.status_message = "Move 10 seconds"
            sp_play = self.service.current_playback()
            if sp_play and "progress_ms" in sp_play and "item" in sp_play:
                cur_pos = sp_play["progress_ms"]
                new_position = cur_pos + 10_000
                track_duration = sp_play["item"]["duration_ms"]
                new_position = min(new_position, track_duration) - 1
                self.service.seek_track(new_position)

        elif command == PlayerCommand.BACK_10s:
            self.status_message = "Back 10 seconds"
            sp_play = self.service.current_playback()
            if sp_play and "progress_ms" in sp_play:
                cur_pos = sp_play["progress_ms"]
                new_position = max(cur_pos - 10_000, 0)
                self.service.seek_track(new_position)

        elif command == PlayerCommand.STOP:
            self.handle_stop()

        elif command == PlayerCommand.LIKE:
            self.handle_like_track()


class SpotifyUI:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, controller: SpotifyController
    ) -> None:
        self.controller = controller
        self.loop = loop
        self._build_interface()
        self.main_loop = urwid.MainLoop(
            self.frame,
            palette=[
                ("normal", "default", "default"),
                ("complete", "default", "dark gray"),
            ],
            unhandled_input=self.handle_input,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

    def _build_interface(self) -> None:
        self.playlist_text = urwid.Text("Current playlist will be displayed here")
        self.playlist_count = urwid.Text("(0)", align="left")
        playlist_count_padded = urwid.Padding(self.playlist_count, align="left", left=1)
        playlist_block = urwid.Columns(
            [
                ("pack", urwid.Text("Playlist: ")),
                ("pack", self.playlist_text),
                ("pack", playlist_count_padded),
            ]
        )

        self.release_date_text = urwid.Text("Date will be displayed here")
        release_date_block = urwid.Columns(
            [("pack", urwid.Text("Release Date: ")), self.release_date_text]
        )

        self.artists_text = urwid.Text("Current artists will be displayed here")
        artists_block = urwid.Columns(
            [("pack", urwid.Text("Artists: ")), self.artists_text]
        )

        self.track_text = urwid.Text("Current track will be displayed here")
        track_block = urwid.Columns([("pack", urwid.Text("Track: ")), self.track_text])

        self.menu_text = urwid.Text("")
        menu_block = urwid.Columns([("pack", urwid.Text("Menu: ")), self.menu_text])

        self.status_text = urwid.Text("Current status will be displayed here")
        status_block = urwid.Columns(
            [("pack", urwid.Text("Status: ")), self.status_text]
        )

        class CustomProgressBar(urwid.ProgressBar):
            def __init__(self, normal, complete, current=0, done=100, text=""):
                super().__init__(normal, complete, current, done)
                self.custom_text = text

            def get_text(self):
                return self.custom_text

            def set_text(self, new_text):
                self.custom_text = new_text

        self.progress = CustomProgressBar(
            "normal", "complete", current=0, done=100, text="0:00/0:00"
        )
        progress_block = urwid.Columns([("fixed", 50, self.progress)])

        self.main_layout = urwid.Pile(
            [
                playlist_block,
                release_date_block,
                artists_block,
                track_block,
                urwid.Divider(),
                menu_block,
                status_block,
                urwid.Divider(),
                progress_block,
            ]
        )
        self.frame = urwid.Frame(body=urwid.SolidFill(" "), footer=self.main_layout)

    def update_ui(self) -> None:
        state = self.controller.state
        if state:
            self.release_date_text.set_text(state.release_date or "No date")
            self.artists_text.set_text(state.artists_repr or "No artists")
            self.track_text.set_text(state.track_repr or "No track")
            pl_text = "No playlist"
            pl_count = 0
            if state.playlist:
                pl_text = state.playlist.name
                pl_count = state.playlist.count
            self.playlist_text.set_text(pl_text)
            self.playlist_count.set_text(f"({pl_count})")
            self.menu_text.set_text(state.cat_menu_repr)
            self.progress.set_text(state.progress_repr)
            self.progress.current = state.progress_percent
        else:
            self.release_date_text.set_text("No date")
            self.playlist_text.set_text("No playlist")
            self.artists_text.set_text("No artists")
            self.track_text.set_text("No track")
            self.menu_text.set_text("")

        self.status_text.set_text(self.controller.status_message)
        self.main_loop.draw_screen()

    def handle_input(self, key: str) -> None:
        base_options = {cmd.value for cmd in PlayerCommand}
        points_options = [
            str(i) for i in range(1, len(self.controller.state.track_points) + 1)
        ]
        if key in base_options:
            self.controller.handle_base_menu(PlayerCommand(key))
        elif key in points_options:
            self.controller.handle_points_menu(int(key))
        elif self.controller.state.cat_menu:
            if isinstance(key, str):
                if key in self.controller.state.cat_menu:
                    self.controller.handle_cat_menu(key)
                elif key.lower() in self.controller.state.cat_menu:
                    self.controller.handle_cat_menu(key.lower(), amplified=True)

        self.update_ui()

    def run(self) -> None:
        self.main_loop.run()


def main() -> None:
    loop = asyncio.get_event_loop()
    service = SpotifyService()
    controller = SpotifyController(service)
    ui = SpotifyUI(loop, controller)

    asyncio.ensure_future(controller.update_state_loop(ui.update_ui))
    ui.run()


if __name__ == "__main__":
    main()
