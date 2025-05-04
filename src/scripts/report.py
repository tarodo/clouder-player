from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.scripts.report_models import get_anthropic_report, get_perplexity_report
from src.scripts.reg_release import register_release
from src.spotycli.mongo_adapter import get_data, save_data_mongo
from src.spotycli.sp_adapter import get_sp_playlist_info

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Vendor(Enum):
    PERPLEXITY = "perplexity"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

@dataclass
class Track:
    sp_track_id: str
    artists: list[str]
    name: str
    position: int

@dataclass
class ReportConfig:
    report_type: str
    system_prompt_version: str
    user_prompt_version: str
    model: str
    vendor: Vendor

@dataclass
class Release:
    name: str
    tracks: list[Track]
    track_list: str
    track_report_config: ReportConfig
    release_report_config: ReportConfig
    tg_post_config: ReportConfig

def get_track_report_config() -> ReportConfig:
    return ReportConfig(
        report_type="track",
        system_prompt_version="v1",
        user_prompt_version="v1",
        model="sonar-pro",
        vendor=Vendor.PERPLEXITY
    )

def get_release_report_config() -> ReportConfig:
    return ReportConfig(
        report_type="release",
        system_prompt_version="v1",
        user_prompt_version="v1",
        model="claude-3-7-sonnet-20250219",
        vendor=Vendor.ANTHROPIC
    )

def get_tg_post_config() -> ReportConfig:
    return ReportConfig(
        report_type="tg_post",
        system_prompt_version="v1",
        user_prompt_version="v1",
        model="claude-3-7-sonnet-20250219",
        vendor=Vendor.ANTHROPIC
    )

def create_release_config(sp_playlist_url: str) -> Release:
    logger.info(f"Creating release data for {sp_playlist_url}")
    sp_playlist = get_sp_playlist_info(sp_playlist_url)
    release_name = sp_playlist["name"]
    sp_tracks = sp_playlist["tracks"]["items"]
    release_tracks = []
    track_list = ""
    for idx, track in enumerate(sp_tracks):
        artists = [artist["name"] for artist in track["track"]["artists"]]
        track_name = track["track"]["name"]
        track_id = track["track"]["id"]
        position = idx + 1
        release_tracks.append(Track(track_id, artists, track_name, position))
        track_list += f"{position}. {', '.join(artists)} - {track_name}\n"
    track_report_config = get_track_report_config()
    release_report_config = get_release_report_config()
    tg_post_config = get_tg_post_config()
    return Release(release_name, release_tracks, track_list, track_report_config, release_report_config, tg_post_config)


def get_prompt(prompt_type: str, report_type: str, prompt_version: str) -> str:
    prompts = get_data("report_prompts", {"prompt_type": prompt_type, "report_type": report_type, "version": prompt_version}, ["prompt"])
    return prompts[0]["prompt"]


def create_tracks_reports(release: Release):
    logger.info(f"Collecting release info for {release.name}")
    track_report_config = release.track_report_config

    track_prompt_version = track_report_config.user_prompt_version
    track_prompt = get_prompt("user", "track", track_prompt_version)
    system_prompt_version = track_report_config.system_prompt_version
    system_prompt = get_prompt("system", "track", system_prompt_version)

    model = track_report_config.model
    vendor = track_report_config.vendor
    for track in release.tracks:
        artist_str = ", ".join(track.artists)
        track_formatted_prompt = track_prompt.format(artist_str, track.name)
        if vendor == Vendor.PERPLEXITY:
            track_content, citations = get_perplexity_report(system_prompt, track_formatted_prompt, model)
        elif vendor == Vendor.ANTHROPIC:
            track_content, citations = get_anthropic_report(system_prompt, track_formatted_prompt, model)
        track_report = {
            "sp_track_id": track.sp_track_id,
            "vendor": vendor.value,
            "version": track_prompt_version,
            "model": model,
            "created": datetime.now().isoformat(),
            "content": track_content,
            "citations": citations
        }
        logger.info(f"Saving track data for '{track.name}' by '{track.artists}'")
        save_data_mongo([track_report], "report_tracks")
        logger.info(f"Saved track data for '{track.name}' by '{track.artists}'")
    logger.info(f"Collected release info for {release.name}")


def collect_tracks_reports(release: Release) -> str:
    logger.info(f"Collecting track data for {release.name}")
    tracks_data = get_data("release_track_reports", {"playlist_name": release.name}, ["track_title", "position", "content", "citations"], [("position", 1)])
    logger.info(f"Collected track data for {release.name}")
    sections = []
    for track_data in tracks_data:
        section = [
            f"Track position: {track_data['position']}",
            f"Track title: {track_data['track_title']}",
            track_data["content"],
            *track_data["citations"],
            "================"
        ]
        sections.append("\n".join(section))
    return "\n\n".join(sections)


def create_release_report(release: Release, all_tracks_reports: str, playlist_specific: str) -> str:
    release_report_config = release.release_report_config
    release_prompt_version = release_report_config.user_prompt_version
    release_prompt_base = get_prompt("user", "playlist", release_prompt_version)
    system_prompt_version = release_report_config.system_prompt_version
    system_prompt = get_prompt("system", "playlist", system_prompt_version)
    release_prompt = release_prompt_base.format(release.name, release.track_list, all_tracks_reports, playlist_specific)

    vendor = release_report_config.vendor
    model = release_report_config.model
    if vendor == Vendor.PERPLEXITY:
        release_content, citations = get_perplexity_report(system_prompt, release_prompt, model)
    elif vendor == Vendor.ANTHROPIC:
        release_content, citations = get_anthropic_report(system_prompt, release_prompt, model)
    release_report = {
        "playlist_name": release.name,
        "vendor": vendor.value,
        "version": release_prompt_version,
        "model": model,
        "created": datetime.now().isoformat(),
        "content": release_content,
        "citations": citations
    }
    save_data_mongo([release_report], "report_releases")
    return release_report

def collect_release_report(release: Release) -> str:
    release_report = get_data("report_releases", {"playlist_name": release.name}, ["content"], [("created", -1)])
    return release_report[0]["content"]

def create_tg_post(release: Release, release_report: str) -> str:
    tg_post_config = release.tg_post_config
    tg_post_prompt_version = tg_post_config.user_prompt_version
    tg_post_prompt_base = get_prompt("user", "tg_post", tg_post_prompt_version)
    system_prompt_version = tg_post_config.system_prompt_version
    system_prompt = get_prompt("system", "tg_post", system_prompt_version)
    tg_post_prompt = tg_post_prompt_base.format(release.name, release_report)

    vendor = tg_post_config.vendor
    model = tg_post_config.model
    if vendor == Vendor.PERPLEXITY:
        tg_post_content, citations = get_perplexity_report(system_prompt, tg_post_prompt, model)
    elif vendor == Vendor.ANTHROPIC:
        tg_post_content, citations = get_anthropic_report(system_prompt, tg_post_prompt, model)
    tg_post = {
        "playlist_name": release.name,
        "vendor": vendor.value,
        "version": tg_post_prompt_version,
        "model": model,
        "created": datetime.now().isoformat(),
        "content": tg_post_content,
        "citations": citations
    }
    save_data_mongo([tg_post], "tg_posts")
    return tg_post

if __name__ == "__main__":
    sp_playlist_url = input("Enter the Spotify playlist URL: ")
    playlist_specifics = [
        (1, "energy and dynamics"),
        (2, "euphoria and impact"),
        (3, "melodic and harmonic"),
        (4, "depth and sorrow"),
    ]
    all_specs = "\n".join([f"{idx}. {spec}" for idx, spec in playlist_specifics])
    user_spec = int(input(f"Enter the user specific details from the following:\n{all_specs}\n"))-1

    register_release(sp_playlist_url)
    release = create_release_config(sp_playlist_url)
    create_tracks_reports(release)
    
    all_tracks_reports = collect_tracks_reports(release)
    create_release_report(release, all_tracks_reports, playlist_specifics[user_spec][1])

    release_report = collect_release_report(release)
    tg_post = create_tg_post(release, release_report)
