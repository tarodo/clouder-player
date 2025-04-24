from src.spotycli.mongo_adapter import save_data_mongo
from src.spotycli.sp_adapter import get_sp_playlist_info


def register_release(release_url: str):    
    sp_release_info = get_sp_playlist_info(release_url)
    release_name = sp_release_info["name"]
    release_description = sp_release_info["description"]
    sp_tracks = sp_release_info["tracks"]["items"]
    release_tracks = []
    for idx, track in enumerate(sp_tracks):
        artists = [{"name": artist["name"], "sp_artist_id": artist["id"]} for artist in track["track"]["artists"]]
        track_info = {
            "sp_track_id": track["track"]["id"],
            "title": track["track"]["name"],
            "artists_str": ", ".join([artist["name"] for artist in artists]),
            "artists": artists,
            "position": idx + 1,
        }
        release_tracks.append(track_info)
    release_playlist = {
        "playlist_name": release_name,
        "sp_playlist_url": release_url,
        "sp_playlist": sp_release_info,
        "playlist_description": release_description,
        "tracks": release_tracks,
    }
    inserted, updated = save_data_mongo([release_playlist], "clouder_releases", ["playlist_name"])
    if inserted > 0:
        print(f"Release {release_name} registered successfully")
    else:
        print(f"Release {release_name} already registered")

if __name__ == "__main__":
    release_url = input("Enter Spotify release URL: ")
    register_release(release_url)
