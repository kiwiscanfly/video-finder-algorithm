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
        response = requests.get(details_url, params=params, timeout=10)
        
        # Check HTTP status code
        if response.status_code != 200:
            print(f"       ✗ Details API HTTP {response.status_code}: {response.reason}")
            if response.status_code == 403:
                print(f"       ✗ Details API quota exceeded or invalid key")
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_info = error_data['error']
                    print(f"       ✗ Details API: {error_info.get('message', 'Unknown error')}")
            except:
                print(f"       ✗ Details response: {response.text[:200]}")
            return []

        data = response.json()
        
        # Check for API errors in response
        if 'error' in data:
            error_info = data['error']
            print(f"       ✗ Details API Error: {error_info.get('message', 'Unknown error')}")
            return []

        if 'items' not in data:
            print(f"       ✗ No video details returned for {len(video_ids)} video IDs")
            return []

        videos = []
        items = data.get('items', [])
        print(f"       → Processing {len(items)} video details...")
        
        for i, item in enumerate(items):
            try:
                video = parse_youtube_video_response(item)
                if is_relevant_coding_video(video):
                    videos.append(video)
            except Exception as e:
                print(f"       ✗ Error parsing video {i+1}: {type(e).__name__}: {e}")
                continue

        print(f"       → {len(videos)} videos passed relevance filter")
        return videos

    except requests.Timeout:
        print(f"       ✗ Details API timeout after 10 seconds")
        return []
    except requests.ConnectionError:
        print(f"       ✗ Details API connection error")
        return []
    except Exception as e:
        print(f"       ✗ Details API unexpected error: {type(e).__name__}: {e}")
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