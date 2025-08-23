import requests
import json
from typing import List, Dict

def get_video_details_from_youtube(api_key: str, video_ids: List[str]) -> List[Dict]:
    if not video_ids:
        return []

    details_url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'key': api_key,
        'id': ','.join(video_ids),
        'part': 'snippet,statistics,contentDetails'
    }

    try:
        response = requests.get(details_url, params=params)
        data = response.json()

        videos = []
        for item in data.get('items', []):
            video = parse_youtube_video_response(item)
            if is_relevant_coding_video(video):
                videos.append(video)

        return videos

    except Exception as e:
        print(f"Error getting video details: {e}")
        return []

def parse_youtube_video_response(item: Dict) -> Dict:
    snippet = item['snippet']
    statistics = item['statistics']

    return {
        'id': item['id'],
        'title': snippet['title'],
        'description': snippet['description'],
        'view_count': int(statistics.get('viewCount', 0)),
        'like_count': int(statistics.get('likeCount', 0)),
        'comment_count': int(statistics.get('commentCount', 0)),
        'duration': item['contentDetails']['duration'],
        'published_at': snippet['publishedAt'],
        'channel_name': snippet['channelTitle'],
        'thumbnail_url': snippet['thumbnails']['high']['url'],
        'tags': json.dumps(snippet.get('tags', [])),
        'category_id': int(snippet.get('categoryId', 0)),
        'url': f"https://www.youtube.com/watch?v={item['id']}"
    }

def is_relevant_coding_video(video: Dict) -> bool:
    title = video['title'].lower()
    description = video['description'].lower()

    programming_keywords = [
        'coding', 'programming', 'javascript', 'python', 'react', 'web development',
        'tutorial', 'learn', 'build', 'create', 'app', 'website', 'algorithm', 'ai'
    ]

    if video['view_count'] < 100000:
        return False

    has_programming = any(keyword in title or keyword in description
                        for keyword in programming_keywords)

    return has_programming