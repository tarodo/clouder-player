from dataclasses import dataclass

import requests
from src.spotycli.sp_adapter import get_sp_playlist_info
from ytmusicapi import YTMusic, OAuthCredentials
from src.spotycli.config import settings


AM_SEARCH_URL = "https://music.apple.com/us/search?term="
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


@dataclass
class Release:
    name: str
    description: str
    tracks: list[tuple[list[str], str]]

def create_release_search_data(sp_playlist_url: str):
    sp_playlist = get_sp_playlist_info(sp_playlist_url)
    release_name = sp_playlist["name"]
    release_description = sp_playlist["description"]
    sp_tracks = sp_playlist["tracks"]["items"]
    release_tracks = []
    for track in sp_tracks:
        artists = [artist["name"] for artist in track["track"]["artists"]]
        track_name = track["track"]["name"]
        release_tracks.append((artists, track_name))
    return Release(release_name, release_description, release_tracks)


def search_am_release(release: Release):
    params = {
        "media": "music",
        "limit": 5
    }

    for track in release.tracks:
        search_term = f"{', '.join(track[0])} {track[1]}"
        item_name = f"{', '.join(track[0])} - {track[1]}"
        am_search_url = f"{AM_SEARCH_URL}{search_term}"
        am_search_url = am_search_url.replace(" ", "%20")
        
        params["term"] = search_term
        response = requests.get(ITUNES_SEARCH_URL, params=params)
        result = response.json()["results"]
        for item in result:
            if item["wrapperType"] == "track" or item["kind"] == "song":
                am_search_url = item["trackViewUrl"]
                break

        print(f"{item_name} :: {am_search_url}")
    print(release.name)
    print(release.description)


def search_yt_release(release: Release) -> str:
    ytmusic = YTMusic("oauth.json", oauth_credentials=OAuthCredentials(client_id=settings.yt_client_id, client_secret=settings.yt_client_secret))
    yt_playlist = ytmusic.create_playlist(release.name, release.description)
    print(f"Created playlist: {yt_playlist}")
    for track in release.tracks:
        yt_tracks = ytmusic.search(f"{', '.join(track[0])} - {track[1]}", "songs")
        if yt_tracks:
            yt_track = yt_tracks[0]
            print(yt_track)
            ytmusic.add_playlist_items(yt_playlist, [yt_track["videoId"]])
    return yt_playlist


if __name__ == "__main__":
    sp_url = input("Enter Spotify release URL: ")
    release = create_release_search_data(sp_url)
    search_yt_release(release)
    search_am_release(release)