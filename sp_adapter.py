import os

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

if not os.getenv("SPOTIPY_CLIENT_ID"):
    from environs import Env

    env = Env()
    env.read_env()


def create_sp():
    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-modify playlist-modify-private"
    return Spotify(
        auth_manager=SpotifyOAuth(scope=scope, open_browser=False, show_dialog=True)
    )


def get_current_track():
    sp = create_sp()
    res = sp.current_playback()
    res["item"]["album"].pop("available_markets", None)
    res["item"].pop("available_markets", None)

    return res


def get_artist_info(artist_id: str):
    sp = create_sp()
    artist_info = sp.artist(artist_id)
    clouder_artist = {
        "id": artist_info["id"],
        "name": artist_info["name"],
        "genres": artist_info["genres"],
        "popularity": artist_info["popularity"],
        "followers": artist_info["followers"]["total"],
    }
    return clouder_artist


get_current_track()
