from typing import List, Dict

def remove_duplicate_videos(videos: List[Dict]) -> List[Dict]:
    seen_ids = set()
    unique_videos = []

    for video in videos:
        if video['id'] not in seen_ids:
            seen_ids.add(video['id'])
            unique_videos.append(video)

    return unique_videos