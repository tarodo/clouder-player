from src.spotycli.mongo_adapter import save_data_mongo
from src.spotycli.sp_adapter import get_sp_playlist_info


def register_release(release_id: str):    
    sp_release_info = get_sp_playlist_info(release_id)
    release_name = sp_release_info["name"]
    release_description = sp_release_info["description"]
    release_playlist = {
        "playlist_name": release_name,
        "sp_playlist": sp_release_info,
        "playlist_description": release_description,
    }
    inserted, updated = save_data_mongo([release_playlist], "clouder_releases", ["playlist_name"])
    if inserted > 0:
        print(f"Release {release_name} registered successfully")
    else:
        print(f"Release {release_name} already registered")

if __name__ == "__main__":
    release_id = input("Enter Spotify release ID: ")
    register_release(release_id)
