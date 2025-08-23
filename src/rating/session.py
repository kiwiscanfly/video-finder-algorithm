from typing import List, Dict

def process_user_rating_for_video(video: Dict, response: str, save_rating_func, get_notes_func):
    if response == 'y':
        notes = get_notes_func(True)
        save_rating_func(video['id'], True, notes)
        print(f"Rated video {video['id']}: 👍")
    elif response == 'n':
        notes = get_notes_func(False)
        save_rating_func(video['id'], False, notes)
        print(f"Rated video {video['id']}: 👎")

def should_continue_rating_session(response: str) -> bool:
    return response != 'q'

def has_videos_to_rate(videos: List[Dict]) -> bool:
    return len(videos) > 0