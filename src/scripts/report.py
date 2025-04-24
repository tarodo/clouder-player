from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import requests
from src.scripts.reg_release import register_release
from src.spotycli.mongo_adapter import get_data, save_data_mongo
from src.spotycli.sp_adapter import get_sp_playlist_info
from src.spotycli.config import settings

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

vendors = {
    "perplexity": "https://api.perplexity.ai",
}

@dataclass
class Track:
    sp_track_id: str
    artists: list[str]
    name: str
    position: int

@dataclass
class Release:
    name: str
    tracks: list[Track]
    vendor: str = "perplexity"
    release_prompt_version: str = "v1"
    track_prompt_version: str = "v1"
    track_system_prompt_version: str = "v1"
    release_model: str = "sonar-pro"
    track_model: str = "sonar-pro"

@dataclass
class TrackData:
    track_title: str
    position: int
    content: str
    citations: list[str]

def create_release_search_data(sp_playlist_url: str):
    logger.info(f"Creating release search data for {sp_playlist_url}")
    sp_playlist = get_sp_playlist_info(sp_playlist_url)
    release_name = sp_playlist["name"]
    sp_tracks = sp_playlist["tracks"]["items"]
    release_tracks = []
    for idx, track in enumerate(sp_tracks):
        artists = [artist["name"] for artist in track["track"]["artists"]]
        track_name = track["track"]["name"]
        track_id = track["track"]["id"]
        position = idx + 1
        release_tracks.append(Track(track_id, artists, track_name, position))
    return Release(release_name, release_tracks)


@lru_cache(maxsize=1000)
def get_prompt(prompt_type: str, prompt_version: str) -> str:
    collection = "report_prompts"
    prompts = get_data(collection, {"type": prompt_type, "version": prompt_version}, ["prompt"])
    return prompts[0]["prompt"]


def collect_track_info(vendor: str, track_prompt: str, system_prompt: str, model: str):
    api_key = settings.perplexity_api_key
    headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    url = f'{vendors[vendor]}/chat/completions'

    data = {
            'model': model,
            'messages': [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": track_prompt
                    }
            ]
        }
    response = requests.post(url, headers=headers, json=data)
    citations = response.json()["citations"]
    content = response.json()["choices"][0]["message"]["content"]
    return {
        "citations": citations,
        "content": content
    }


def collect_tracks_info(release: Release):
    logger.info(f"Collecting release info for {release.name}")
    vendor = release.vendor
    track_prompt_version = release.track_prompt_version
    track_prompt = get_prompt("track_info", track_prompt_version)
    system_prompt_version = release.track_system_prompt_version
    system_prompt = get_prompt("track_info_system", system_prompt_version)
    model = release.track_model
    for track in release.tracks:
        artist_str = ", ".join(track.artists)
        track_formatted_prompt = track_prompt.format(artist_str, track.name)
        track_data = collect_track_info(vendor, track_formatted_prompt, system_prompt, model)
        track_data["sp_track_id"] = track.sp_track_id
        track_data["vendor"] = vendor
        track_data["version"] = track_prompt_version
        track_data["model"] = model
        track_data["created"] = datetime.now().isoformat()
        logger.info(f"Saving track data for {track.name} by {track.artists}")
        save_data_mongo([track_data], "report_tracks")
        logger.info(f"Saved track data for {track.name} by {track.artists}")
    logger.info(f"Collected release info for {release.name}")


def collect_track_data(release: Release) -> list[TrackData]:
    logger.info(f"Collecting track data for {release.name}")
    tracks_data = get_data("release_track_reports", {"playlist_name": release.name}, ["track_title", "position", "content", "citations"], [("position", 1)])
    logger.info(f"Collected track data for {release.name}")
    result = []
    for track_data in tracks_data:
        one_track_data = TrackData(track_data["track_title"], track_data["position"], track_data["content"], track_data["citations"])
        result.append(one_track_data)
    return result


def build_full_release_data(tracks_data: list[TrackData]):
    full_release_data = ""
    for track_data in tracks_data:
        full_release_data += f"Track position: {track_data.position}\nTrack title: {track_data.track_title}\n"
        full_release_data += track_data.content
        full_release_data += "\n"
        full_release_data += "\n".join(track_data.citations)
        full_release_data += "\n\n"
        full_release_data += "================"
        full_release_data += "\n\n"
    return full_release_data

if __name__ == "__main__":
    sp_playlist_url = input("Enter the Spotify playlist URL: ")
    register_release(sp_playlist_url)
    release = create_release_search_data(sp_playlist_url)
    release.vendor = "perplexity"
    release.track_prompt_version = "v1"
    release.track_system_prompt_version = "v1"
    release.track_model = "sonar-pro"
    collect_tracks_info(release)
    tracks_data = collect_track_data(release)
    full_release_data = build_full_release_data(tracks_data)
    
    with open("examples/full_release_data.txt", "w") as f:
        f.write(full_release_data)
