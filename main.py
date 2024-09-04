import asyncio
import logging
from dataclasses import dataclass

import urwid
from environs import Env
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from urwid import Widget

from mongo_adapter import get_sp_clouder_week_by_pl_id

logger = logging.getLogger("sp")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler("logs/sp.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.propagate = False

from enum import StrEnum


class PlayerCommand(StrEnum):
    NEXT = ">"
    PREVIOUS = "<"
    MOVE_10s = "."
    BACK_10s = ","
    STOP = " "
    LIKE = "l"


TRACK_POINTS = 5

env = Env()
env.read_env()


def create_sp() -> Spotify:
    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-modify playlist-modify-private"
    return Spotify(
        auth_manager=SpotifyOAuth(scope=scope, open_browser=False, show_dialog=True)
    )


@dataclass
class PlayerState:
    track_id: int
    track_name: str
    artists: dict[str, str]
    duration_ms: int
    playlist_id: int | None = None
    playlist_name: str | None = None
    is_clouder: bool | None = None
    is_base_playlist: bool | None = None
    extra_playlists: dict[str, str] | None = None
    trash_playlist_id: int | None = None


class SpotifyUI:
    def __init__(self, loop):
        self._base_menu_options = [command.value for command in PlayerCommand]
        self._points_menu_options = [str(i) for i in range(1, TRACK_POINTS + 1)]
        self._extra_menu_options = None
        self.sp = create_sp()

        # Interface elements
        self.main_layout: Widget | None = None
        self.frame: Widget | None = None

        self.playlist_text: Widget | None = None
        self.artists_text: Widget | None = None
        self.track_text: Widget | None = None
        self.menu_text: Widget | None = None
        self.status_text: Widget | None = None

        self._player_state: PlayerState | None = None

        self.create_interface()

        self.loop_widget = urwid.MainLoop(
            self.frame,
            unhandled_input=self.handle_input,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
        )
        asyncio.ensure_future(self.update_player_state())

    def create_interface(self):
        playlist_stat = urwid.Text("Playlist: ")
        self.playlist_text = urwid.Text("Current playlist will be displayed here")
        playlist_block = urwid.Columns(
            [
                ("pack", urwid.Padding(playlist_stat, align="left")),
                ("pack", urwid.Padding(self.playlist_text, align="left")),
            ]
        )

        artists_stat = urwid.Text("Artists: ")
        self.artists_text = urwid.Text("Current artists will be displayed here")
        artists_block = urwid.Columns(
            [
                ("pack", urwid.Padding(artists_stat, align="left")),
                ("pack", urwid.Padding(self.artists_text, align="left")),
            ]
        )

        track_stat = urwid.Text("Track: ")
        self.track_text = urwid.Text("Current track will be displayed here")
        track_block = urwid.Columns(
            [
                ("pack", urwid.Padding(track_stat, align="left")),
                ("pack", urwid.Padding(self.track_text, align="left")),
            ]
        )

        status_stat = urwid.Text("Status: ")
        self.status_text = urwid.Text("Current status will be displayed here")
        status_block = urwid.Columns(
            [
                ("pack", urwid.Padding(status_stat, align="left")),
                ("pack", urwid.Padding(self.status_text, align="left")),
            ]
        )

        menu_stat = urwid.Text("Menu: ")
        self.menu_text = urwid.Text("")
        menu_block = urwid.Columns(
            [
                ("pack", urwid.Padding(menu_stat, align="left")),
                ("pack", urwid.Padding(self.menu_text, align="left")),
            ]
        )

        self.main_layout = urwid.Pile(
            [
                playlist_block,
                artists_block,
                track_block,
                urwid.Divider(),
                menu_block,
                status_block,
                urwid.Divider(),
            ]
        )

        self.frame = urwid.Frame(body=urwid.SolidFill(" "), footer=self.main_layout)

    def clear_player_state(self):
        self._player_state = None

    def is_same_track(self, current_playback):
        current_player = self._player_state
        return (
            current_player and current_player.track_id == current_playback["item"]["id"]
        )

    async def get_playlist_data(self, current_playback):
        context_type = current_playback["context"]["type"]
        if context_type != "playlist":
            return {}

        playlist_id = current_playback["context"]["uri"].split(":")[-1]
        current_player = self._player_state

        if current_player and current_player.playlist_id == playlist_id:
            return {
                "playlist_id": playlist_id,
                "playlist_name": current_player.playlist_name,
                "is_clouder": current_player.is_clouder,
                "is_base_playlist": current_player.is_base_playlist,
                "extra_playlists": current_player.extra_playlists,
                "trash_playlist_id": current_player.trash_playlist_id,
            }

        clouder_week = await get_sp_clouder_week_by_pl_id(playlist_id)
        if not clouder_week:
            return {"playlist_id": playlist_id}

        clouder_pl = clouder_week.get("sp_playlists", {}).get(playlist_id)
        if not clouder_pl:
            return {"playlist_id": playlist_id}

        playlist_name = clouder_pl.get("sp_name")
        is_clouder = True
        is_base_playlist = clouder_pl.get("clouder_type") == "base"
        extra_playlists = (
            {
                pl_info["clouder_name"]: pl_id
                for pl_id, pl_info in clouder_week.get("sp_playlists").items()
                if pl_info["clouder_type"] == "extra"
            }
            if is_base_playlist
            else {}
        )

        trash_playlist_id = None
        for pl_id, pl_info in clouder_week.get("sp_playlists").items():
            if pl_info["clouder_name"] == "trash":
                trash_playlist_id = pl_id

        return {
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "is_clouder": is_clouder,
            "is_base_playlist": is_base_playlist,
            "extra_playlists": extra_playlists,
            "trash_playlist_id": trash_playlist_id,
        }

    def update_extra_menu(self):
        if not self._player_state or not self._player_state.extra_playlists:
            return
        self._extra_menu_options = [
            opt[:1].lower() for opt in self._player_state.extra_playlists.keys()
        ]
        logger.info(f"Extra menu options: {self._extra_menu_options}")
        self.loop_widget.draw_screen()

    def update_player_ui(self):
        player_state = self._player_state
        if not player_state:
            return
        artists = ", ".join(player_state.artists.values())
        self.track_text.set_text(player_state.track_name or "No track")
        self.artists_text.set_text(artists or "No artists")
        self.playlist_text.set_text(player_state.playlist_name or "No playlist")
        menu_text = (
            ", ".join(
                opt.capitalize() for opt in self._player_state.extra_playlists.keys()
            )
            if self._player_state.extra_playlists
            else ""
        )
        self.menu_text.set_text(menu_text)
        self.loop_widget.draw_screen()

    async def update_player_state(self):
        while True:
            await asyncio.sleep(1)
            logger.info(f"Player state start: {self._player_state}")

            current_playback = self.sp.current_playback()
            if not current_playback:
                self.clear_player_state()
                continue

            if self.is_same_track(current_playback):
                continue

            playlist_data = await self.get_playlist_data(current_playback)

            self._player_state = PlayerState(
                track_id=current_playback["item"]["id"],
                track_name=current_playback["item"]["name"],
                duration_ms=current_playback["item"]["duration_ms"],
                artists={
                    art["id"]: art["name"]
                    for art in current_playback["item"]["artists"]
                },
                **playlist_data,
            )
            self.update_extra_menu()
            self.update_player_ui()

            logger.info(f"Player state updated: {self._player_state}")

    def calculate_position(self, point: int, total: int = 5) -> int:
        duration = self._player_state.duration_ms
        return int((point - 1) * duration / total)

    def handle_next_track(self, need_info: bool = True):
        if need_info:
            self.status_text.set_text("Next track")
        if (
            self._player_state.is_base_playlist
            and self._player_state.playlist_id != self._player_state.trash_playlist_id
        ):
            self.sp.playlist_add_items(
                self._player_state.trash_playlist_id, [self._player_state.track_id]
            )
            self.sp.playlist_remove_all_occurrences_of_items(
                self._player_state.playlist_id, [self._player_state.track_id]
            )
        self.sp.next_track()

    def handle_stop(self):
        cur_state = self.sp.current_playback()
        if cur_state:
            if cur_state["is_playing"]:
                self.status_text.set_text("Stop track")
                self.sp.pause_playback()
            else:
                self.status_text.set_text("Resume track")
                self.sp.start_playback()

    def handle_base_menu(self, command: PlayerCommand):
        if command == PlayerCommand.NEXT:
            self.handle_next_track()

        elif command == PlayerCommand.PREVIOUS:
            self.status_text.set_text("Previous track")
            try:
                self.sp.previous_track()
            except Exception as e:
                self.handle_points_menu(1)

        elif command == PlayerCommand.MOVE_10s:
            self.status_text.set_text("Move 10 seconds")
            sp_play = self.sp.current_playback()
            if sp_play and "progress_ms" in sp_play:
                cur_pos = sp_play["progress_ms"]
                new_position = cur_pos + 10000
                track_duration = sp_play["item"]["duration_ms"]
                new_position = min(new_position, track_duration) - 1
                self.sp.seek_track(new_position)

        elif command == PlayerCommand.BACK_10s:
            self.status_text.set_text("Back 10 seconds")
            sp_play = self.sp.current_playback()
            if sp_play and "progress_ms" in sp_play:
                cur_pos = sp_play["progress_ms"]
                new_position = cur_pos - 10000
                new_position = max(new_position, 0)
                self.sp.seek_track(new_position)
        elif command == PlayerCommand.STOP:
            self.handle_stop()

        elif command == PlayerCommand.LIKE:
            self.status_text.set_text("Like track")
            track_id = self._player_state.track_id
            if track_id:
                self.sp.current_user_saved_tracks_add([track_id])

    def handle_points_menu(self, point: int):
        self.status_text.set_text(f"Move to {point} point")
        new_position = self.calculate_position(point)
        self.sp.seek_track(new_position)

    def handle_input(self, key):
        if key in self._base_menu_options:
            self.handle_base_menu(PlayerCommand(key))

        if key in self._points_menu_options:
            self.handle_points_menu(int(key))

        if self._extra_menu_options and key in self._extra_menu_options:
            for pl_name in self._player_state.extra_playlists.keys():
                if key == pl_name[:1].lower():
                    pl_id = self._player_state.extra_playlists[pl_name]
                    self.sp.playlist_add_items(pl_id, [self._player_state.track_id])
                    self.handle_next_track(need_info=False)
                    self.status_text.set_text(f"Move to {pl_name} playlist :: {pl_id}")
                    break

    def run(self):
        self.loop_widget.run()


def main():
    loop = asyncio.get_event_loop()
    app = SpotifyUI(loop)
    app.run()


if __name__ == "__main__":
    main()
