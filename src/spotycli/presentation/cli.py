import asyncio
import logging
from collections.abc import Callable
from enum import StrEnum

import urwid

from src.spotycli.application.services import PlayerApplicationService
from src.spotycli.domain.models import PlayerState
from src.spotycli.infrastructure.spotify_adapter import SpotifyAdapter

logger = logging.getLogger("main") # Or a new "presentation" logger


class PlayerCommand(StrEnum):
    NEXT = ">"
    PREVIOUS = "<"
    MOVE_10s = "."
    BACK_10s = ","
    STOP = " "
    LIKE = "!"


class CliController:
    def __init__(self, app_service: PlayerApplicationService) -> None:
        self.app_service = app_service
        self.spotify_adapter = app_service.spotify_adapter
        self.state: PlayerState | None = None
        self.status_message: str = ""

    async def update_state_loop(self, update_ui_callback: Callable[[], None]) -> None:
        while True:
            await asyncio.sleep(1)
            await self.update_state(update_ui_callback)

    async def update_state(self, update_ui_callback: Callable[[], None]) -> None:
        self.state = self.app_service.get_current_playback_state()
        update_ui_callback()

    def handle_next_track(self) -> None:
        self.status_message = "Next track"
        if (
            self.state
            and self.state.playlist
            and self.state.playlist.is_base_pl
            and self.state.playlist.clouder_pl_type != "trash"
        ):
            self.spotify_adapter.add_to_playlist(
                self.state.playlist.base_playlists["trash"], self.state.id
            )
            self.spotify_adapter.remove_from_playlist(self.state.playlist.id, self.state.id)
        if self.state:
             self.app_service.update_playlist_count_in_state(self.state)
        self.spotify_adapter.next_track()

    def handle_stop(self) -> None:
        cur_state_data = self.spotify_adapter.current_playback()
        if cur_state_data:
            if cur_state_data.get("is_playing"):
                self.status_message = "Stop track"
                self.spotify_adapter.pause_playback()
            else:
                self.status_message = "Resume track"
                self.spotify_adapter.start_playback()

    def handle_points_menu(self, point: int) -> None:
        if not self.state or not self.state.track_points:
            return
        self.status_message = f"Move to {point} point"
        new_position = self.state.track_points[point - 1]
        self.spotify_adapter.seek_track(new_position)

    def handle_move_track(self, pl_name: str, amplified: bool = False) -> None:
        if not self.state:
            return
        pl_id = self.state.cat_menu[pl_name]
        self.spotify_adapter.add_if_not_exists(pl_id, self.state.id)
        status_msg = f"'{self.state.name}' Moved to {pl_name.capitalize()}"
        if self.state.playlist and not self.state.playlist.is_base_pl:
            self.spotify_adapter.remove_from_playlist(
                self.state.playlist.id, self.state.id
            )
        if amplified:
            clouder_pl = self.state.playlist
            if (
                clouder_pl
                and clouder_pl.prep_playlists
                and pl_name in clouder_pl.prep_playlists
            ):
                prep_pl_id = clouder_pl.prep_playlists[pl_name]
                self.spotify_adapter.add_if_not_exists(prep_pl_id, self.state.id)
                status_msg += " (amplified)"
        self.handle_next_track()  # This also updates playlist count via app_service
        self.status_message = status_msg

    def handle_like_track(self) -> None:
        if not self.state or not self.state.id:
            return
        msg = f"'{self.state.name}' Like track"
        clouder_pl = self.state.playlist
        if clouder_pl and not clouder_pl.is_base_pl and clouder_pl.prep_playlists:
            cat_name = clouder_pl.clouder_pl_name
            if cat_name in clouder_pl.prep_playlists:
                prep_pl_id = clouder_pl.prep_playlists[cat_name]
                self.spotify_adapter.add_if_not_exists(prep_pl_id, self.state.id)
                msg = f"'{self.state.name}' Like track (amplified)"
        else:
            self.spotify_adapter.like_track(self.state.id)
        self.status_message = msg

    def handle_base_menu(self, command: PlayerCommand) -> None:
        if command == PlayerCommand.NEXT:
            self.handle_next_track()
        elif command == PlayerCommand.PREVIOUS:
            self.status_message = "Previous track"
            try:
                self.spotify_adapter.previous_track()
            except Exception: # Spotify API might error if no previous track
                self.handle_points_menu(1) # Rewind to start

        elif command == PlayerCommand.MOVE_10s:
            self.status_message = "Move 10 seconds"
            sp_play = self.spotify_adapter.current_playback()
            if sp_play and "progress_ms" in sp_play and "item" in sp_play and sp_play["item"]:
                cur_pos = sp_play["progress_ms"]
                new_position = cur_pos + 10_000
                track_duration = sp_play["item"]["duration_ms"]
                new_position = min(new_position, track_duration) - 1
                self.spotify_adapter.seek_track(new_position)

        elif command == PlayerCommand.BACK_10s:
            self.status_message = "Back 10 seconds"
            sp_play = self.spotify_adapter.current_playback()
            if sp_play and "progress_ms" in sp_play:
                cur_pos = sp_play["progress_ms"]
                new_position = max(cur_pos - 10_000, 0)
                self.spotify_adapter.seek_track(new_position)

        elif command == PlayerCommand.STOP:
            self.handle_stop()

        elif command == PlayerCommand.LIKE:
            self.handle_like_track()


class SpotifyUI:
    def __init__(self, loop: asyncio.AbstractEventLoop, controller: CliController) -> None:
        self.controller = controller

        # Initialize UI widgets
        self.playlist_text = urwid.Text("Current playlist will be displayed here")
        self.playlist_count = urwid.Text("(0)", align="left")
        playlist_count_padded = urwid.Padding(self.playlist_count, align="left", left=1)
        self.playlist_block = urwid.Columns(
            [
                ("pack", urwid.Text("Playlist: ")),
                ("pack", self.playlist_text),
                ("pack", playlist_count_padded),
            ]
        )
        self.release_date_text = urwid.Text("Date will be displayed here")
        self.artists_text = urwid.Text("Current artists will be displayed here")
        self.album_text = urwid.Text("Current album will be displayed here")
        self.track_text = urwid.Text("Current track will be displayed here")
        self.menu_text = urwid.Text("")
        self.status_text = urwid.Text("Current status will be displayed here")

        class CustomProgressBar(urwid.ProgressBar):
            def __init__(self, normal, complete, current=0, done=100, text=""):
                super().__init__(normal, complete, current, done)
                self.custom_text = text

            def get_text(self):
                return self.custom_text

            def set_text(self, new_text):
                self.custom_text = new_text

        self.progress = CustomProgressBar("normal", "complete", text="0:00/0:00")
        self.main_layout = urwid.Pile(
            [
                self.playlist_block,
                urwid.Columns(
                    [("pack", urwid.Text("Release Date: ")), self.release_date_text]
                ),
                urwid.Columns([("pack", urwid.Text("Artists: ")), self.artists_text]),
                urwid.Columns([("pack", urwid.Text("Album: ")), self.album_text]),
                urwid.Columns([("pack", urwid.Text("Track: ")), self.track_text]),
                urwid.Divider(),
                urwid.Columns([("pack", urwid.Text("Menu: ")), self.menu_text]),
                urwid.Columns([("pack", urwid.Text("Status: ")), self.status_text]),
                urwid.Divider(),
                urwid.Columns([("fixed", 50, self.progress)]),
            ]
        )
        self.frame = urwid.Frame(body=urwid.SolidFill(" "), footer=self.main_layout)
        
        # Create urwid MainLoop with asyncio event loop
        self.main_loop = urwid.MainLoop(
            self.frame,
            palette=[
                ("normal", "default", "default"),
                ("complete", "default", "dark gray"),
            ],
            unhandled_input=self.handle_input,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )

    def update_ui(self) -> None:
        state = self.controller.state
        if state:
            self.release_date_text.set_text(state.release_date or "No date")
            self.artists_text.set_text(state.artists_repr or "No artists")
            self.album_text.set_text(state.album_repr or "No album")
            self.track_text.set_text(state.track_repr or "No track")
            pl_text, pl_count = ("No playlist", 0)
            if state.playlist:
                pl_text = state.playlist.name
                pl_count = state.playlist.count
            self.playlist_text.set_text(pl_text)
            self.playlist_count.set_text(f"({pl_count})")
            self.menu_text.set_text(state.cat_menu_repr)
            self.progress.set_text(state.progress_repr)
            self.progress.current = state.progress_percent
        else:
            for widget in [self.release_date_text, self.playlist_text, self.artists_text, self.album_text, self.track_text, self.menu_text]:
                widget.set_text("N/A" if widget != self.menu_text else "")
            self.playlist_count.set_text("(0)")
            self.progress.set_text("0:00/0:00")
            self.progress.current = 0

        self.status_text.set_text(self.controller.status_message)
        self.main_loop.draw_screen()

    def handle_input(self, key: str) -> None:
        if key == "q":
            raise urwid.ExitMainLoop()

        if not self.controller.state:  # No state, no further actions
            return

        base_options = {cmd.value for cmd in PlayerCommand}
        points_options = []
        if self.controller.state.track_points:
            points_options = [
                str(i) for i in range(1, len(self.controller.state.track_points) + 1)
            ]

        if key in base_options:
            self.controller.handle_base_menu(PlayerCommand(key))
        elif key in points_options:
            self.controller.handle_points_menu(int(key))
        elif key in self.controller.state.cat_menu:
            self.controller.handle_cat_menu(key)
        elif isinstance(key, str) and key.lower() in self.controller.state.cat_menu:
            self.controller.handle_cat_menu(key.lower(), amplified=True)
        self.update_ui()

    def run(self) -> None:
        logger.info("Starting SpotiCLI UI...")
        self.main_loop.run() 