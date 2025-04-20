from src.spotycli.sp_adapter import get_sp_playlist_tracks_full

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    playlist_url = input("Enter Spotify playlist URL: ")
    with open("examples/playlist.txt", "w") as f:
        all_tracks = []
        pl_info = get_sp_playlist_tracks_full(playlist_url)
        for track in pl_info:
            f.write(f"{track}\n")
            all_tracks.append(f"'{track}'")

        print(f"[{','.join(all_tracks)}]")