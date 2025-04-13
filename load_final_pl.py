from src.spotycli.sp_adapter import get_sp_playlist_tracks_full

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    with open("examples/playlist.txt", "w") as f:
        pl_info = get_sp_playlist_tracks_full("https://open.spotify.com/playlist/0TyzgwEmwr5EIfJNu0iA55?si=d6bcb9b3b320477d")
        for track in pl_info:
            f.write(f"{track}\n")

