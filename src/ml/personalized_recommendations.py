"""
Enhanced personalization service that combines manual ratings with YouTube user data
for improved video recommendations.
"""

from typing import List, Dict, Optional
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from src.auth.youtube_user_service import YouTubeUserService
from src.database.connection import get_database_connection
from src.ml.feature_extraction import extract_all_features_from_video
from src.ml.predictions import predict_video_preferences_with_model


class PersonalizedRecommendationService:
    """
    Service for generating personalized recommendations using both manual ratings
    and YouTube user data.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize personalized recommendation service.
        
        Args:
            db_path: Database path
        """
        self.db_path = db_path
        self.youtube_user_service = YouTubeUserService(db_path)
    
    def get_enhanced_recommendations(self, user_id: str, model, video_features: pd.DataFrame, 
                                   top_n: int = 24) -> List[Dict]:
        """
        Get enhanced recommendations combining ML model with YouTube data.
        
        Args:
            user_id: User ID for OAuth
            model: Trained ML model
            video_features: DataFrame with video features
            top_n: Number of recommendations to return
            
        Returns:
            List of enhanced recommendations
        """
        # Get base ML predictions
        base_recommendations = predict_video_preferences_with_model(model, video_features, top_n * 2)
        
        # Get user's YouTube tags for content similarity
        youtube_tags = self.youtube_user_service.get_youtube_tags_for_personalization(user_id)
        
        if not youtube_tags:
            # No YouTube data available, return base recommendations
            return base_recommendations[:top_n]
        
        # Enhance recommendations with content similarity
        enhanced_recommendations = self._enhance_with_content_similarity(
            base_recommendations, youtube_tags, video_features
        )
        
        # Apply YouTube engagement patterns
        final_recommendations = self._apply_engagement_patterns(
            enhanced_recommendations, user_id
        )
        
        return final_recommendations[:top_n]
    
    def _enhance_with_content_similarity(self, recommendations: List[Dict], 
                                       youtube_tags: List[str], 
                                       video_features: pd.DataFrame) -> List[Dict]:
        """
        Enhance recommendations using content similarity with YouTube history.
        
        Args:
            recommendations: Base recommendations from ML model
            youtube_tags: Tags extracted from user's YouTube history
            video_features: Full video features DataFrame
            
        Returns:
            Enhanced recommendations with content similarity scores
        """
        if not youtube_tags or video_features.empty:
            return recommendations
        
        try:
            # Create user interest profile from YouTube tags
            user_profile = ' '.join(youtube_tags)
            
            # Get video content for similarity calculation
            video_contents = []
            video_ids = []
            
            for _, row in video_features.iterrows():
                # Combine title, description, and channel name for content representation
                content = f"{row['title']} {row.get('description', '')} {row['channel_name']}"
                video_contents.append(content.lower())
                video_ids.append(row['id'])
            
            if not video_contents:
                return recommendations
            
            # Calculate content similarity using TF-IDF
            vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
            
            # Fit on video content + user profile
            all_content = video_contents + [user_profile.lower()]
            tfidf_matrix = vectorizer.fit_transform(all_content)
            
            # Calculate similarity between user profile and each video
            user_vector = tfidf_matrix[-1]  # Last vector is user profile
            video_vectors = tfidf_matrix[:-1]  # All other vectors are videos
            
            similarities = cosine_similarity(user_vector, video_vectors)[0]
            
            # Create similarity mapping
            similarity_map = dict(zip(video_ids, similarities))
            
            # Enhance recommendations with content similarity
            for rec in recommendations:
                video_id = rec['id']
                content_similarity = similarity_map.get(video_id, 0.0)
                
                # Combine ML probability with content similarity
                ml_score = rec.get('like_probability', 0.5)
                content_score = min(content_similarity * 2, 1.0)  # Scale similarity
                
                # Weighted combination (70% ML, 30% content similarity)
                enhanced_score = (ml_score * 0.7) + (content_score * 0.3)
                rec['like_probability'] = enhanced_score
                rec['content_similarity'] = content_similarity
            
            # Re-sort by enhanced score
            recommendations.sort(key=lambda x: x['like_probability'], reverse=True)
            
            return recommendations
            
        except Exception as e:
            print(f"Error in content similarity enhancement: {e}")
            return recommendations
    
    def _apply_engagement_patterns(self, recommendations: List[Dict], user_id: str) -> List[Dict]:
        """
        Apply user's YouTube engagement patterns to boost relevant content.
        
        Args:
            recommendations: Enhanced recommendations
            user_id: User ID
            
        Returns:
            Recommendations with engagement pattern boosts
        """
        try:
            # Get cached user data for engagement patterns
            user_data = self.youtube_user_service.get_cached_user_data(user_id)
            
            if not user_data:
                return recommendations
            
            # Analyze engagement patterns from liked videos and subscriptions
            patterns = self._analyze_engagement_patterns(user_data)
            
            # Apply pattern-based boosts
            for rec in recommendations:
                boost_factor = self._calculate_pattern_boost(rec, patterns)
                
                # Apply boost to probability
                current_prob = rec.get('like_probability', 0.5)
                boosted_prob = min(current_prob * boost_factor, 1.0)
                rec['like_probability'] = boosted_prob
                rec['pattern_boost'] = boost_factor
            
            # Re-sort by boosted probability
            recommendations.sort(key=lambda x: x['like_probability'], reverse=True)
            
            return recommendations
            
        except Exception as e:
            print(f"Error applying engagement patterns: {e}")
            return recommendations
    
    def _analyze_engagement_patterns(self, user_data: Dict) -> Dict:
        """
        Analyze user's engagement patterns from YouTube data.
        
        Args:
            user_data: User's YouTube data
            
        Returns:
            Dictionary with engagement patterns
        """
        patterns = {
            'popular_channels': set(),
            'preferred_video_length': 'medium',  # short/medium/long
            'topic_preferences': set(),
            'view_count_preference': 'moderate'  # low/moderate/high
        }
        
        try:
            # Analyze liked videos
            liked_videos = user_data.get('liked_videos', [])
            
            if liked_videos:
                # Channel preferences
                channel_counts = {}
                view_counts = []
                
                for video in liked_videos:
                    channel = video.get('channel_name', '')
                    if channel:
                        channel_counts[channel] = channel_counts.get(channel, 0) + 1
                    
                    # Collect view counts for preference analysis
                    view_count = video.get('view_count', 0)
                    if view_count > 0:
                        view_counts.append(view_count)
                
                # Top channels (liked 2+ videos from)
                patterns['popular_channels'] = {
                    channel for channel, count in channel_counts.items() 
                    if count >= 2
                }
                
                # View count preference
                if view_counts:
                    median_views = np.median(view_counts)
                    if median_views > 1000000:
                        patterns['view_count_preference'] = 'high'
                    elif median_views > 100000:
                        patterns['view_count_preference'] = 'moderate'
                    else:
                        patterns['view_count_preference'] = 'low'
            
            # Analyze subscriptions for topic preferences
            subscriptions = user_data.get('subscriptions', [])
            for sub in subscriptions:
                title = sub.get('title', '').lower()
                description = sub.get('description', '').lower()
                
                # Extract topic keywords
                tech_keywords = ['tech', 'programming', 'coding', 'software', 'development']
                tutorial_keywords = ['tutorial', 'learn', 'course', 'education']
                
                if any(kw in title or kw in description for kw in tech_keywords):
                    patterns['topic_preferences'].add('tech')
                if any(kw in title or kw in description for kw in tutorial_keywords):
                    patterns['topic_preferences'].add('tutorial')
            
            return patterns
            
        except Exception as e:
            print(f"Error analyzing engagement patterns: {e}")
            return patterns
    
    def _calculate_pattern_boost(self, recommendation: Dict, patterns: Dict) -> float:
        """
        Calculate boost factor based on engagement patterns.
        
        Args:
            recommendation: Video recommendation
            patterns: User's engagement patterns
            
        Returns:
            Boost factor (1.0 = no boost, >1.0 = boost, <1.0 = penalty)
        """
        boost = 1.0
        
        try:
            # Channel preference boost
            channel = recommendation.get('channel_name', '')
            if channel in patterns['popular_channels']:
                boost *= 1.2  # 20% boost for preferred channels
            
            # View count preference alignment
            view_count = recommendation.get('view_count', 0)
            view_pref = patterns['view_count_preference']
            
            if view_pref == 'high' and view_count > 1000000:
                boost *= 1.1
            elif view_pref == 'moderate' and 100000 <= view_count <= 1000000:
                boost *= 1.1
            elif view_pref == 'low' and view_count < 100000:
                boost *= 1.1
            
            # Topic preference boost (based on title/content)
            title = recommendation.get('title', '').lower()
            if 'tech' in patterns['topic_preferences'] and any(
                kw in title for kw in ['programming', 'coding', 'tech', 'software']
            ):
                boost *= 1.15
            
            if 'tutorial' in patterns['topic_preferences'] and any(
                kw in title for kw in ['tutorial', 'learn', 'guide', 'how to']
            ):
                boost *= 1.15
            
            return min(boost, 1.5)  # Cap boost at 50%
            
        except Exception as e:
            print(f"Error calculating pattern boost: {e}")
            return 1.0
    
    def get_personalization_stats(self, user_id: str) -> Dict:
        """
        Get statistics about personalization enhancement.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with personalization statistics
        """
        try:
            # Get YouTube data
            user_data = self.youtube_user_service.get_cached_user_data(user_id)
            if not user_data:
                user_data = self.youtube_user_service.get_user_youtube_data(user_id)
            
            if not user_data:
                return {'error': 'No YouTube data available'}
            
            # Get tags for personalization
            tags = self.youtube_user_service.get_youtube_tags_for_personalization(user_id)
            
            # Analyze patterns
            patterns = self._analyze_engagement_patterns(user_data)
            
            # Get manual rating count
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM preferences')
                manual_ratings = cursor.fetchone()[0]
            
            return {
                'youtube_data': {
                    'liked_videos': len(user_data.get('liked_videos', [])),
                    'subscriptions': len(user_data.get('subscriptions', [])),
                    'activities': len(user_data.get('activities', []))
                },
                'personalization_tags': len(tags),
                'manual_ratings': manual_ratings,
                'engagement_patterns': {
                    'preferred_channels': len(patterns['popular_channels']),
                    'topic_preferences': list(patterns['topic_preferences']),
                    'view_count_preference': patterns['view_count_preference']
                },
                'enhancement_level': 'high' if len(tags) > 20 and manual_ratings > 10 else 'moderate'
            }
            
        except Exception as e:
            return {'error': f'Failed to get personalization stats: {str(e)}'}