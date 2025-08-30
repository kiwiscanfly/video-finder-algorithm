import requests
from typing import List, Dict

from src.services.youtube_client import YouTubeAPIClient
from src.config.app_config import DEFAULT_CODING_QUERIES

def search_youtube_videos_by_query(api_key: str, query: str, max_results: int) -> List[str]:
    """
    Legacy function for backward compatibility.
    Uses the new unified YouTubeAPIClient internally.
    """
    client = YouTubeAPIClient(api_key)
    return client.search_videos(query, max_results)

def get_coding_search_queries() -> List[str]:
    """
    Get default coding search queries.
    Uses centralized configuration.
    """
    return DEFAULT_CODING_QUERIES