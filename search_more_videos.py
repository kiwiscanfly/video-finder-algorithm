#!/usr/bin/env python3
import os
from dotenv import load_dotenv

from src.config.app_config import AppConfig
from src.services.video_search_service import VideoSearchService

load_dotenv()

def search_more_videos():
    """Search for additional coding videos using the VideoSearchService."""
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment variables")
        return

    print("🔍 Searching for more coding videos...")

    # Use different/additional search queries to find new videos
    additional_queries = [
        "python tutorial",
        "web development course",
        "coding interview prep",
        "javascript frameworks",
        "database tutorial",
        "react tutorial",
        "node.js tutorial",
        "data structures algorithms",
        "system design",
        "software engineering"
    ]

    # Use VideoSearchService for clean, unified search
    search_service = VideoSearchService(api_key, AppConfig.DATABASE_PATH)
    unique_videos = search_service.search_and_save_videos(
        queries=additional_queries,
        max_results_per_query=AppConfig.DEFAULT_RESULTS_PER_QUERY
    )

    if unique_videos:
        print(f"✅ Found and saved {len(unique_videos)} new videos!")
    else:
        print("❌ No new videos found.")

if __name__ == "__main__":
    search_more_videos()