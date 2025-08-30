import requests
import json
from typing import List, Dict

from src.services.youtube_client import YouTubeAPIClient

def get_video_details_from_youtube(api_key: str, video_ids: List[str]) -> List[Dict]:
    """
    Legacy function for backward compatibility.
    Uses the new unified YouTubeAPIClient internally.
    """
    client = YouTubeAPIClient(api_key)
    return client.get_video_details(video_ids)

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