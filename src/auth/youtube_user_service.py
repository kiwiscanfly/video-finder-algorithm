"""
YouTube user data service for accessing user's YouTube information via OAuth.
Retrieves liked videos, subscriptions, and channel activities.
"""

import json
from typing import List, Dict, Optional, Any
from datetime import datetime

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from src.auth.oauth_service import OAuthService
from src.database.connection import get_database_connection


class YouTubeUserService:
    """
    Service for accessing YouTube user data through OAuth authentication.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize YouTube user service.
        
        Args:
            db_path: Database path
        """
        self.db_path = db_path
        self.oauth_service = OAuthService(db_path)
    
    def get_user_youtube_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive YouTube data for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with liked videos, subscriptions, channel info, or None
        """
        credentials = self.oauth_service.get_user_credentials(user_id)
        if not credentials:
            return None
        
        try:
            # Build YouTube service
            youtube = googleapiclient.discovery.build(
                'youtube', 'v3', credentials=credentials
            )
            
            # Get user's channel info
            channels_response = youtube.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if not channels_response.get('items'):
                return None
            
            channel = channels_response['items'][0]
            channel_id = channel['id']
            
            # Collect all data
            user_data = {
                'channel_info': {
                    'id': channel_id,
                    'title': channel['snippet']['title'],
                    'description': channel['snippet']['description'],
                    'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
                    'video_count': int(channel['statistics'].get('videoCount', 0)),
                    'view_count': int(channel['statistics'].get('viewCount', 0))
                },
                'liked_videos': self._get_liked_videos(youtube),
                'subscriptions': self._get_subscriptions(youtube),
                'activities': self._get_recent_activities(youtube)
            }
            
            # Cache data in database
            self._cache_user_data(user_id, user_data)
            
            return user_data
            
        except HttpError as e:
            print(f"YouTube API error: {e}")
            return None
        except Exception as e:
            print(f"Error fetching YouTube data: {e}")
            return None
    
    def get_cached_user_data(self, user_id: str, max_age_hours: int = 24) -> Optional[Dict[str, Any]]:
        """
        Get cached YouTube data if fresh enough.
        
        Args:
            user_id: User ID
            max_age_hours: Maximum age of cached data in hours
            
        Returns:
            Cached data or None
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT youtube_data, updated_at 
                    FROM youtube_user_data 
                    WHERE user_id = ?
                ''', (user_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Check if data is fresh enough
                updated_at = datetime.fromisoformat(row[1])
                age_hours = (datetime.now() - updated_at).total_seconds() / 3600
                
                if age_hours <= max_age_hours:
                    return json.loads(row[0])
                
                return None
                
        except Exception as e:
            print(f"Error getting cached data: {e}")
            return None
    
    def get_youtube_tags_for_personalization(self, user_id: str) -> List[str]:
        """
        Extract tags from YouTube data for personalization.
        
        Args:
            user_id: User ID
            
        Returns:
            List of tags from liked videos and subscriptions
        """
        # Try cached data first
        user_data = self.get_cached_user_data(user_id)
        if not user_data:
            # Fetch fresh data
            user_data = self.get_user_youtube_data(user_id)
        
        if not user_data:
            return []
        
        tags = set()
        
        # Extract tags from liked videos
        for video in user_data.get('liked_videos', []):
            if video.get('tags'):
                for tag in video['tags']:
                    if isinstance(tag, str) and tag.strip():
                        tags.add(tag.strip().lower())
        
        # Extract keywords from subscriptions (channel names and descriptions)
        for subscription in user_data.get('subscriptions', []):
            # Add channel name as keywords
            channel_title = subscription.get('title', '').lower()
            if channel_title:
                # Split channel name into potential keywords
                keywords = channel_title.replace('_', ' ').replace('-', ' ').split()
                for keyword in keywords:
                    if len(keyword) > 2:  # Skip very short words
                        tags.add(keyword)
        
        return list(tags)
    
    def _get_liked_videos(self, youtube, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get user's liked videos.
        
        Args:
            youtube: YouTube API client
            max_results: Maximum number of videos to retrieve
            
        Returns:
            List of liked video data
        """
        try:
            liked_videos = []
            next_page_token = None
            
            while len(liked_videos) < max_results:
                request = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    myRating='like',
                    maxResults=min(50, max_results - len(liked_videos)),
                    pageToken=next_page_token
                )
                
                response = request.execute()
                
                for item in response.get('items', []):
                    video_data = {
                        'id': item['id'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'channel_name': item['snippet']['channelTitle'],
                        'tags': item['snippet'].get('tags', []),
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'published_at': item['snippet']['publishedAt'],
                        'duration': item['contentDetails']['duration']
                    }
                    liked_videos.append(video_data)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return liked_videos
            
        except HttpError as e:
            print(f"Error fetching liked videos: {e}")
            return []
    
    def _get_subscriptions(self, youtube, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get user's subscriptions.
        
        Args:
            youtube: YouTube API client
            max_results: Maximum number of subscriptions to retrieve
            
        Returns:
            List of subscription data
        """
        try:
            subscriptions = []
            next_page_token = None
            
            while len(subscriptions) < max_results:
                request = youtube.subscriptions().list(
                    part='snippet',
                    mine=True,
                    maxResults=min(50, max_results - len(subscriptions)),
                    pageToken=next_page_token
                )
                
                response = request.execute()
                
                for item in response.get('items', []):
                    subscription_data = {
                        'channel_id': item['snippet']['resourceId']['channelId'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt']
                    }
                    subscriptions.append(subscription_data)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return subscriptions
            
        except HttpError as e:
            print(f"Error fetching subscriptions: {e}")
            return []
    
    def _get_recent_activities(self, youtube, max_results: int = 25) -> List[Dict[str, Any]]:
        """
        Get user's recent activities.
        
        Args:
            youtube: YouTube API client
            max_results: Maximum number of activities to retrieve
            
        Returns:
            List of activity data
        """
        try:
            request = youtube.activities().list(
                part='snippet,contentDetails',
                mine=True,
                maxResults=max_results
            )
            
            response = request.execute()
            activities = []
            
            for item in response.get('items', []):
                activity_data = {
                    'type': item['snippet']['type'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt']
                }
                activities.append(activity_data)
            
            return activities
            
        except HttpError as e:
            print(f"Error fetching activities: {e}")
            return []
    
    def _cache_user_data(self, user_id: str, user_data: Dict[str, Any]):
        """
        Cache user's YouTube data in database.
        
        Args:
            user_id: User ID
            user_data: YouTube data to cache
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO youtube_user_data 
                    (user_id, youtube_data, updated_at)
                    VALUES (?, ?, datetime('now'))
                ''', (user_id, json.dumps(user_data)))
                
        except Exception as e:
            print(f"Error caching user data: {e}")