import requests
from typing import List, Dict

def search_youtube_videos_by_query(api_key: str, query: str, max_results: int) -> List[Dict]:
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'key': api_key,
        'q': query,
        'part': 'snippet',
        'type': 'video',
        'order': 'viewCount',
        'maxResults': max_results,
        'videoCategoryId': '28',
        'publishedAfter': '2020-01-01T00:00:00Z'
    }

    try:
        response = requests.get(search_url, params=params, timeout=10)
        
        # Check HTTP status code
        if response.status_code != 200:
            print(f"       ✗ HTTP {response.status_code}: {response.reason}")
            if response.status_code == 403:
                print(f"       ✗ API quota exceeded or invalid key")
            elif response.status_code == 400:
                print(f"       ✗ Bad request - check API parameters")
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_info = error_data['error']
                    print(f"       ✗ {error_info.get('message', 'Unknown error')}")
                    if 'errors' in error_info:
                        for err in error_info['errors']:
                            print(f"       ✗ {err.get('reason', '')}: {err.get('message', '')}")
            except:
                print(f"       ✗ Response: {response.text[:200]}")
            return []

        data = response.json()
        
        # Check for API errors in response
        if 'error' in data:
            error_info = data['error']
            print(f"       ✗ API Error: {error_info.get('message', 'Unknown error')}")
            if error_info.get('code') == 403:
                print(f"       ✗ Quota exceeded or permission denied")
            return []

        # Check if we have items
        if 'items' not in data:
            print(f"       - No 'items' in response")
            if 'pageInfo' in data:
                total_results = data['pageInfo'].get('totalResults', 0)
                print(f"       - Total results available: {total_results}")
            return []

        if len(data['items']) == 0:
            print(f"       - Empty results for query")
            return []

        video_ids = [item['id']['videoId'] for item in data['items']]
        return video_ids

    except requests.Timeout:
        print(f"       ✗ Request timeout after 10 seconds")
        return []
    except requests.ConnectionError:
        print(f"       ✗ Connection error - check internet connection")
        return []
    except KeyError as e:
        print(f"       ✗ Missing expected data field: {e}")
        print(f"       ✗ Response structure: {list(data.keys()) if 'data' in locals() else 'No data'}")
        return []
    except Exception as e:
        print(f"       ✗ Unexpected error: {type(e).__name__}: {e}")
        return []

def get_coding_search_queries() -> List[str]:
    return [
        "coding passion project ideas",
        "weekend programming projects",
        "creative coding projects",
        "fun programming side projects",
        "indie developer projects",
        "building passion projects programming",
        "personal coding project showcase",
        "hobby programming projects",
        "weekend coding challenge",
        "solo developer projects",
        "build something cool programming",
        "coding project inspiration",
        "unique programming projects",
        "developer side project success",
        "open source passion projects"
    ]