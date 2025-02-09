from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth


def create_sp():
    scope = (
        "user-read-playback-state user-modify-playback-state "
        "user-read-currently-playing user-library-modify playlist-modify-private"
    )
    return Spotify(
        auth_manager=SpotifyOAuth(scope=scope, open_browser=False, show_dialog=True)
    )


def get_sp_artist(artist_id: str):
    sp = create_sp()
    artist_info = sp.artist(artist_id)

    return artist_info
