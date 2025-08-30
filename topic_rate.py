#!/usr/bin/env python3
"""
Search for YouTube videos on a topic and immediately rate them.
Combines topic-based search with interactive rating session.
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict, Optional

from src.database.manager import setup_database_tables
from src.database.video_operations import save_videos_to_database, save_video_features_to_database
from src.database.preference_operations import save_video_rating_to_database, get_rated_count_from_database
from src.youtube.search import search_youtube_videos_by_query
from src.youtube.details import get_video_details_from_youtube
from src.youtube.utils import remove_duplicate_videos
from src.ml.feature_extraction import extract_all_features_from_video
from src.ollama.keyword_generator import (
    generate_keywords_from_topic, 
    fallback_manual_keywords,
    check_ollama_running
)
from src.rating.display import display_video_information_for_rating, display_rating_session_header, display_session_type_message
from src.rating.user_input import get_user_rating_response, get_user_notes_for_rating
from src.rating.session import process_user_rating_for_video, should_continue_rating_session


def check_api_quota_status(api_key: str) -> bool:
    """Quick check to see if YouTube API is working."""
    from src.youtube.search import search_youtube_videos_by_query
    try:
        # Try a simple search to test quota
        result = search_youtube_videos_by_query(api_key, "test", 1)
        return True  # If no exception, quota is working
    except:
        return False


class TopicRatingSession:
    """Manages topic-based video search and rating."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.db_path = "video_inspiration.db"
        self.session_videos = []
        self.topic = ""
        self.session_id = None
        
    def search_videos_for_topic(self, topic: str, use_fallback: bool = False) -> List[Dict]:
        """
        Search for videos based on a topic.
        
        Args:
            topic: The topic to search for
            use_fallback: Use fallback keyword generation
            
        Returns:
            List of unique videos found
        """
        self.topic = topic
        self.session_id = datetime.now().isoformat()
        
        print(f"\n🎯 Topic: {topic}")
        print("=" * 50)
        
        # Generate search keywords
        if use_fallback:
            print("📝 Using fallback keyword generation...")
            keywords = fallback_manual_keywords(topic)
        else:
            print("🤖 Generating search keywords with Ollama...")
            keywords = generate_keywords_from_topic(topic, num_queries=10)
            
            if not keywords:
                print("⚠️  Falling back to manual keyword generation...")
                keywords = fallback_manual_keywords(topic)
        
        if not keywords:
            print("❌ Could not generate keywords for this topic.")
            return []
        
        print(f"\n📋 Generated {len(keywords)} search queries")
        print("\n🔍 Searching YouTube for videos...")
        print("-" * 40)
        
        all_videos = []
        
        # Search with fewer queries to get manageable number of videos for rating
        for i, query in enumerate(keywords[:8], 1):  # Limit to 8 queries
            print(f"  [{i}/8] Searching: {query[:50]}...")
            
            try:
                video_ids = search_youtube_videos_by_query(self.api_key, query, 3)  # Only 3 per query
                
                if video_ids:
                    videos = get_video_details_from_youtube(self.api_key, video_ids)
                    all_videos.extend(videos)
                    total_found += len(videos)
                    print(f"       ✓ Found {len(videos)} videos")
                else:
                    # Check if this looks like a quota issue on first query
                    if i == 1:  # First query failed
                        print(f"       - No videos found (possible quota exceeded)")
                        print(f"       💡 YouTube API quota resets daily at midnight PT")
                        break  # Don't continue if quota is exceeded
                    else:
                        print(f"       - No videos found")
                    
            except Exception as e:
                print(f"       ✗ Error: {str(e)}")
        
        # Remove duplicates
        unique_videos = remove_duplicate_videos(all_videos)
        
        print(f"\n📊 Found {len(unique_videos)} unique videos for rating")
        
        if unique_videos:
            # Save to database with session tracking
            self._save_videos_with_session(unique_videos)
            
        return unique_videos
    
    def _save_videos_with_session(self, videos: List[Dict]):
        """Save videos to database with session tracking."""
        # Add session metadata to each video
        for video in videos:
            video['search_session'] = self.session_id
            video['search_topic'] = self.topic
        
        # Save videos and extract features
        save_videos_to_database(videos, self.db_path)
        
        for video in videos:
            features = extract_all_features_from_video(video)
            save_video_features_to_database(video['id'], features, self.db_path)
    
    def get_unrated_videos_from_session(self) -> List[Dict]:
        """Get unrated videos from the current search session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get videos from this session that haven't been rated
        cursor.execute('''
            SELECT v.*
            FROM videos v
            LEFT JOIN preferences p ON v.id = p.video_id
            WHERE p.video_id IS NULL
            AND v.id IN ({})
            ORDER BY v.view_count DESC
        '''.format(','.join(['?'] * len(self.session_videos))), 
        [v['id'] for v in self.session_videos])
        
        videos = []
        for row in cursor.fetchall():
            videos.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'view_count': row[3],
                'like_count': row[4],
                'comment_count': row[5],
                'duration': row[6],
                'published_at': row[7],
                'channel_name': row[8],
                'thumbnail_url': row[9],
                'tags': row[10],
                'url': f"https://youtube.com/watch?v={row[0]}"
            })
        
        conn.close()
        return videos
    
    def start_rating_session(self, videos: List[Dict]):
        """Start an interactive rating session for the found videos."""
        if not videos:
            print("❌ No videos to rate!")
            return
        
        self.session_videos = videos
        
        print("\n" + "=" * 50)
        print("📺 RATING SESSION")
        print("=" * 50)
        print(f"Topic: {self.topic}")
        print(f"Videos to rate: {len(videos)}")
        print("\nInstructions:")
        print("  y = Like this video")
        print("  n = Don't like this video")
        print("  q = Quit rating session")
        print("-" * 50)
        
        rated_in_session = 0
        
        for i, video in enumerate(videos, 1):
            # Check if video was already rated (in case of duplicates across topics)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT video_id FROM preferences WHERE video_id = ?', (video['id'],))
            if cursor.fetchone():
                conn.close()
                continue  # Skip already rated videos
            conn.close()
            
            print(f"\n[{i}/{len(videos)}] Video from topic: {self.topic}")
            print("-" * 40)
            
            display_video_information_for_rating(video)
            
            response = get_user_rating_response()
            
            if not should_continue_rating_session(response):
                print(f"\n✅ Rated {rated_in_session} videos from '{self.topic}'")
                return
            
            def save_rating(video_id, liked, notes):
                save_video_rating_to_database(video_id, liked, notes, self.db_path)
            
            process_user_rating_for_video(video, response, save_rating, get_user_notes_for_rating)
            rated_in_session += 1
        
        print(f"\n✅ Completed rating session for '{self.topic}'")
        print(f"   Rated {rated_in_session} videos")
        
        # Show overall progress
        total_rated = get_rated_count_from_database(self.db_path)
        print(f"\n📊 Total videos rated overall: {total_rated}")
        
        if total_rated >= 10:
            print("🤖 ML model is now active for recommendations!")


def main():
    """Main entry point for topic-based rating."""
    parser = argparse.ArgumentParser(
        description="Search for videos on a topic and rate them immediately"
    )
    parser.add_argument(
        "--topic", 
        "-t",
        type=str, 
        help="The topic to search for"
    )
    parser.add_argument(
        "--fallback",
        "-f",
        action="store_true",
        help="Use fallback keyword generation (no Ollama required)"
    )
    parser.add_argument(
        "--continuous",
        "-c",
        action="store_true",
        help="Continue with multiple topics"
    )
    
    args = parser.parse_args()
    
    load_dotenv()
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in environment variables")
        return
    
    # Setup database
    setup_database_tables("video_inspiration.db")
    
    # Create session manager
    session = TopicRatingSession(api_key)
    
    # Main loop for topic rating
    while True:
        # Get topic
        if args.topic and not args.continuous:
            topic = args.topic
        else:
            print("\n🎯 Topic-Based Video Rating")
            print("=" * 40)
            
            if not args.fallback and not check_ollama_running():
                print("⚠️  Ollama is not running")
                print("   To use AI keyword generation, start Ollama with:")
                print("   $ ollama serve")
                print("\n   Or use --fallback flag for basic keyword generation")
                response = input("\nContinue with fallback mode? (y/n): ")
                if response.lower() != 'y':
                    print("Exiting...")
                    sys.exit(0)
                args.fallback = True
            
            topic = input("\n📝 Enter topic to search and rate (or 'quit' to exit): ").strip()
            
            if topic.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not topic:
                print("❌ Topic cannot be empty")
                continue
        
        # Check API quota before searching
        print("🔍 Checking YouTube API status...")
        if not check_api_quota_status(api_key):
            print("❌ YouTube API quota exceeded or API key invalid")
            print("💡 YouTube API quota resets daily at midnight Pacific Time")
            print("   You can still rate existing videos in the database")
            if input("Continue anyway? (y/n): ").lower() != 'y':
                continue
        
        # Search for videos
        videos = session.search_videos_for_topic(topic, use_fallback=args.fallback)
        
        if videos:
            # Start rating session
            print("\n⏸️  Press Enter to start rating these videos...")
            input()
            session.start_rating_session(videos)
        else:
            print("❌ No videos found for this topic.")
        
        # Check if we should continue
        if not args.continuous:
            if args.topic:  # If topic was provided via CLI, exit after one session
                break
            
            another = input("\n🔄 Search and rate another topic? (y/n): ")
            if another.lower() != 'y':
                break
        
        # Clear the CLI topic for next iteration
        args.topic = None
    
    print("\n🏁 Session complete!")
    total_rated = get_rated_count_from_database("video_inspiration.db")
    print(f"📊 Total videos rated: {total_rated}")
    
    if total_rated >= 10:
        print("\n💡 You can now use the dashboard to see AI-powered recommendations!")
        print("   Run: python dashboard_api.py")


if __name__ == "__main__":
    main()