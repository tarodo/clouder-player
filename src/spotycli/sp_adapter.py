from pprint import pprint

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


def get_sp_playlist_tracks(playlist_id: str, limit: int = 100):
    sp = create_sp()
    track_uris = []
    offset = 0
    while True:
        playlist_data = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        tracks = playlist_data['items']
        if not tracks:
            break
        for track in tracks:
            track_uris.append(track['track']['id'])
        offset += limit
    return track_uris


def get_sp_playlist_tracks_full(playlist_id: str, limit: int = 100):
    sp = create_sp()
    track_uris = []
    offset = 0
    while True:
        playlist_data = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        tracks = playlist_data['items']
        if not tracks:
            break
        for track in tracks:
            artists = [artist['name'] for artist in track['track']['artists']]
            artists_str = ', '.join(artists)
            full_repr = f"{artists_str} - {track['track']['name']}"
            track_uris.append(full_repr)
        offset += limit
    return track_uris

