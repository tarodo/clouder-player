"""
Module for registering clouder week playlists in the database.
"""

from src.spotycli.sp_adapter import get_sp_playlist_tracks
from src.spotycli.clouder_adapter import get_playlists
from src.spotycli.mongo_adapter import save_data_mongo

def register_week_playlists(week: str):
    _, week_playlists = get_playlists(week)
    if not week_playlists:
        return

    records_to_update = []
    for pl_name, sp_playlist_id in week_playlists.items():
        tracks = get_sp_playlist_tracks(sp_playlist_id)
        records_to_update.append({
            "clouder_week": week,
            "clouder_pl_name": pl_name,
            "sp_tracks": tracks
        })

    save_data_mongo(records_to_update, "sp_playlists", ["clouder_week", "clouder_pl_name"])
    


if __name__ == "__main__":
    register_week_playlists("DNB_2025_7")
