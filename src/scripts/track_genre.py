from dataclasses import dataclass
import json

from src.scripts.report_models import get_perplexity_report
from src.spotycli.mongo_adapter import get_data, get_mongo_conn, save_data_mongo


@dataclass
class TrackGenre:
    sp_id: str
    bp_id: str
    name: str
    artists: list[str]
    label: str
    key: str
    bpm: str

def collect_tracks(playlist_id: str) -> list[TrackGenre]:
    aggregation = [
        {
            "$match": {
                "playlist_id": playlist_id
            }
        },
        {
            "$unwind": "$sp_tracks"
        },
        {
            "$lookup": {
                "from": "sp_tracks",
                "localField": "sp_tracks",
                "foreignField": "id",
                "as": "track_info"
            }
        },
        {
            "$unwind": "$track_info"
        },
        {
            "$project": {
                "_id": 0,
                "sp_id": "$track_info.id",
                "bp_id": "$track_info.bp_id",
                "name": "$track_info.name",
                "artists": {
                    "$map": {
                        "input": "$track_info.artists",
                        "as": "artist",
                        "in": "$$artist.name"
                    }
                }
            }
        }
        ]
    mongo_db = get_mongo_conn()
    sp_tracks = list(mongo_db["sp_playlists"].aggregate(aggregation))

    all_bp_ids = set()
    for track in sp_tracks:
        all_bp_ids.add(track["bp_id"])
    
    bp_tracks = {
        track["id"]: track
        for track in mongo_db["bp_tracks"].find(
            {"id": {"$in": list(all_bp_ids)}},
            {
                "_id": 0,
                "id": 1,
                "bpm": 1, 
                "key": "$key.name",
                "label": "$release.label.name"
            }
        )
    }

    track_data = []
    for track in sp_tracks:
        sp_id = track["sp_id"]
        bp_id = int(track["bp_id"])
        artists = track["artists"]
        name = track["name"]
        bp_track = bp_tracks.get(bp_id)
        if bp_track:
            bpm = bp_track["bpm"]
            key = bp_track["key"]
            label = bp_track["label"]
            track_data.append(TrackGenre(sp_id, bp_id, name, artists, label, key, bpm))
        else:
            continue

    return track_data

def collect_genres(track: TrackGenre):
    print(f"collecting genres for {track.name} by {track.artists}")
    system_prompt = """
    You're an electronic music expert specializing in Drum and Bass.
    """

    prompt = """
    Determine sub-genres of Drum and Bass for:
        - Artist(s): {artists}
        - Title: {name}
        - Label: {label}
        - BPM: {bpm}
        - Key: {music_key}

    Search the label's official page, Reddit, YouTube comments, and other available sources.
    If no official sub-genre is mentioned, check the artists' previous releases and the label's typical genre focus.
    Sub-genres list:
        'ambient', 'atmospheric', 'breakcore', 'breakbeat',
        'chillout', 'dark', 'darkcore', 'darkstep', 
        'deep', 'downtempo', 'downbeat', 'dub', 'dubstep', 
        'half-time', 'intelligent', 'jazzstep', 'jump up', 'jungle', 
        'liquid', 'minimal', 'neurofunk', 
        'rollers', 'soulful', 'techstep'
    Return JSON only:
    {{
        "sub-genres": ["sub-genres from the list above confirmed from credible sources"],
        "predicted sub-genres": ["sub-genres from the list above based on style, artist history, or label focus"],
        "label sub-genres": ["sub-genres of the label from the list above"],
        "other info": "brief notes on sound, comparisons, or label tendencies"
    }}
    Rules:
	- Only add to sub-genres if explicitly confirmed.
	- Use predicted sub-genres for reasonable assumptions.
	- Keep other info concise but informative.

    """
    track_prompt = prompt.format(
        artists=', '.join(track.artists),
        name=track.name,
        label=track.label,
        bpm=track.bpm,
        music_key=track.key
    )

    # result = get_perplexity_report(system_prompt, track_prompt, "sonar-pro")
    # print(result)
    # print("=============")
    genres, _ = get_perplexity_report(system_prompt, track_prompt, "sonar")
    return genres


def get_genres(track_genre_txt: str) -> list[str]:
    import re
    dnb_names = ["dnb", "drum and bass", "drum & bass", "drum n bass", "drumnbass", "drum'n'bass", "drumandbass"]
    matches = re.findall(r'\[(.*?)\]', track_genre_txt, re.DOTALL)
    all_blocks = [m for m in matches if len(m) > 1]
    result = []
    for block in all_blocks:
        block_parts = block.split(",")
        for genre in block_parts:
            genre = genre.replace("'", "")
            genre = genre.replace('"', '')
            genre = genre.lower()
            for dnb_name in dnb_names:
                genre = genre.replace(dnb_name, "")
            genre = genre.strip()
            result.append(genre)
    result_set = set([g for g in result if len(g) > 0])
    return list(result_set)

def save_track_genre(track: TrackGenre, genres_txt: str, genres: list[str], clouder_genre: str):
    data = {
        "sp_id": track.sp_id,
        "bp_id": track.bp_id,
        "name": track.name,
        "artists": track.artists,
        "label": track.label,
        "bpm": track.bpm,
        "key": track.key,
        "genres_txt": genres_txt,
        "genres_list": genres,
        "clouder_genre": clouder_genre
    }
    save_data_mongo([data], "track_genres", ["sp_id"])


def collect_clouder_genre(clouder_genre: str):
    data = get_data("track_genres", {"clouder_genre": clouder_genre}, {"_id": 0, "genres_list": 1, "genres_txt": 1})
    genres_list = [g for d in data for g in d["genres_list"]]
    genres_set = set(genres_list)
    all_genres_txt = [d["genres_txt"] for d in data]
    return genres_set, all_genres_txt

def collect_all_genres():
    full_genres_set = set()
    for genre in playlists_to_collect.values():
        genres_set, genres_txt = collect_clouder_genre(genre)
        full_genres_set.update(genres_set)
    
    ordered_genres = list(full_genres_set)
    ordered_genres.sort()
    with open("examples/genres/ordered_genres.json", "w") as f:
        json.dump(ordered_genres, f, indent=4)

if __name__ == "__main__":
    playlists_to_collect = {
    }
    for playlist_id, clouder_genre in playlists_to_collect.items():
        tracks = collect_tracks(playlist_id)
        for track in tracks:
            track_genre_txt = collect_genres(track)
            track_genres = get_genres(track_genre_txt)
            save_track_genre(track, track_genre_txt, track_genres, clouder_genre)
    
    collect_all_genres()