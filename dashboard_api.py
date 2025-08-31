import os
import requests
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import secrets
from functools import wraps

from src.config.app_config import AppConfig, OAuthConfig
from src.database.manager import setup_database_tables
from src.database.connection import get_database_connection
from src.database.preference_operations import get_training_data_from_database, get_unrated_videos_with_features_from_database, get_rated_count_from_database, save_video_rating_to_database, remove_video_preference
from src.database.search_operations import get_recent_search_sessions, get_videos_by_search_session, get_search_sessions_stats, cleanup_old_search_sessions, delete_search_session, create_search_session, update_search_session_video_count
from src.services.video_search_service import TopicVideoSearchService
from src.database.video_operations import get_unrated_videos_from_database
from src.ml.model_training import create_recommendation_model, train_model_on_user_preferences
from src.ml.predictions import predict_video_preferences_with_model
from src.auth.oauth_service import OAuthService
from src.auth.youtube_user_service import YouTubeUserService
from src.ml.personalized_recommendations import PersonalizedRecommendationService

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Configure session settings
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Now using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600  # 1 hour
)

# Configure CORS to allow credentials (needed for sessions)
CORS(app, supports_credentials=True, origins=['https://localhost:5001'])

class DashboardAPI:
    def __init__(self):
        self.db_path = AppConfig.DATABASE_PATH
        self.model = None
        self.model_trained = False
        self.oauth_service = OAuthService(self.db_path)
        self.youtube_user_service = YouTubeUserService(self.db_path)
        self.personalized_service = PersonalizedRecommendationService(self.db_path)
        setup_database_tables(self.db_path)
        self._initialize_model()

    def _initialize_model(self):
        rated_count = get_rated_count_from_database(self.db_path)
        if rated_count >= AppConfig.ML_TRAINING_THRESHOLD:
            self.model = create_recommendation_model()
            training_data = get_training_data_from_database(self.db_path)
            success = train_model_on_user_preferences(self.model, training_data)
            if success:
                self.model_trained = True

    def get_recommendations(self, user_id: str = None):
        if self.model_trained and self.model:
            video_features = get_unrated_videos_with_features_from_database(self.db_path)
            
            # Use enhanced personalization if user is authenticated and has YouTube data
            if user_id:
                try:
                    recommendations = self.personalized_service.get_enhanced_recommendations(
                        user_id, self.model, video_features, top_n=24
                    )
                    return recommendations
                except Exception as e:
                    print(f"Enhanced personalization failed, falling back to standard: {e}")
                    # Fall back to standard ML recommendations
            
            # Standard ML recommendations
            recommendations = predict_video_preferences_with_model(self.model, video_features, top_n=24)
            return recommendations  # Return 24 videos for dashboard
        else:
            fallback_videos = get_unrated_videos_from_database(24, self.db_path)
            for video in fallback_videos:
                video['like_probability'] = 0.5  # Default probability
            return fallback_videos
    
    def get_liked_videos(self):
        """Get videos that user liked, ordered by AI match confidence"""
        import sqlite3
        
        try:
            with get_database_connection(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get liked videos with features
                query = """
                SELECT v.*, vf.*, p.liked
                FROM videos v 
                JOIN video_features vf ON v.id = vf.video_id
                JOIN preferences p ON v.id = p.video_id
                WHERE p.liked = 1
                ORDER BY v.view_count DESC
                """
                
                cursor.execute(query)
                results = cursor.fetchall()
            
            liked_videos = []
            for row in results:
                video = {
                    'id': row['id'],
                    'title': row['title'],
                    'channel_name': row['channel_name'],
                    'view_count': row['view_count'],
                    'url': f"https://www.youtube.com/watch?v={row['id']}"
                }
                liked_videos.append(video)
            
            # If model is trained, predict confidence for liked videos
            if self.model_trained and self.model and liked_videos:
                # Create pandas DataFrame for prediction
                import pandas as pd
                
                df_data = []
                for row in results:
                    row_data = {
                        'id': row['id'],
                        'title': row['title'],
                        'channel_name': row['channel_name'],
                        'view_count': row['view_count'],
                        'title_length': row['title_length'],
                        'description_length': row['description_length'],
                        'view_like_ratio': row['view_like_ratio'],
                        'engagement_score': row['engagement_score'],
                        'title_sentiment': row['title_sentiment'],
                        'has_tutorial_keywords': row['has_tutorial_keywords'],
                        'has_beginner_keywords': row['has_beginner_keywords'],
                        'has_ai_keywords': row['has_ai_keywords'],
                        'has_challenge_keywords': row['has_challenge_keywords'],
                        'has_time_constraint': row['has_time_constraint']
                    }
                    df_data.append(row_data)
                
                video_features_df = pd.DataFrame(df_data)
                
                # Get predictions for confidence scores
                predictions = predict_video_preferences_with_model(self.model, video_features_df)
                
                # Sort by confidence and return
                return sorted(predictions, key=lambda x: x.get('like_probability', 0), reverse=True)
            
            # If no model, return with default confidence
            for video in liked_videos:
                video['like_probability'] = 0.8  # High default for liked videos
                
            return liked_videos
            
        except Exception as e:
            print(f"Error getting liked videos: {e}")
            return []

dashboard_api = DashboardAPI()

def oauth_required(f):
    """Decorator to require OAuth authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'auth_required': True
            }), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# OAuth routes
@app.route('/auth/login')
def oauth_login():
    """Initiate OAuth login flow."""
    try:
        if not OAuthConfig.is_configured():
            return jsonify({
                'success': False,
                'error': 'OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.'
            }), 500
        
        # Generate and store state for security
        state = secrets.token_urlsafe(32)
        session['oauth_state'] = state
        
        # Also store in database as backup
        with get_database_connection(dashboard_api.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('INSERT OR REPLACE INTO oauth_states (state) VALUES (?)', (state,))
            
        print(f"Debug - Generated state: {state}")
        print(f"Debug - Stored in session: {session.get('oauth_state')}")
        print(f"Debug - Also stored in database")
        
        # Get authorization URL
        auth_url, _ = dashboard_api.oauth_service.get_authorization_url(state)
        print(f"Debug - Auth URL: {auth_url}")
        
        return redirect(auth_url)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OAuth login failed: {str(e)}'
        }), 500

@app.route('/auth/callback')
def oauth_callback():
    """Handle OAuth callback."""
    try:
        # Debug logging
        state = request.args.get('state')
        session_state = session.get('oauth_state')
        print(f"Debug - Received state: {state}")
        print(f"Debug - Session state: {session_state}")
        print(f"Debug - Session contents: {dict(session)}")
        
        # Verify state parameter (check session first, then database)
        state_valid = False
        if state and state == session_state:
            state_valid = True
            print("Debug - State validated from session")
        elif state:
            # Check database as fallback
            with get_database_connection(dashboard_api.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT state FROM oauth_states WHERE state = ?', (state,))
                if cursor.fetchone():
                    state_valid = True
                    # Clean up used state
                    cursor.execute('DELETE FROM oauth_states WHERE state = ?', (state,))
                    print("Debug - State validated from database")
        
        if not state_valid:
            error_msg = f'Invalid state parameter. Received: {state}, Expected: {session_state}'
            print(f"Debug - State validation failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': 'Invalid state parameter',
                'debug': error_msg if app.debug else None
            }), 400
        
        # Handle authorization response
        authorization_response = request.url
        user_info = dashboard_api.oauth_service.handle_authorization_callback(
            authorization_response, state
        )
        
        if not user_info:
            return jsonify({
                'success': False,
                'error': 'OAuth authentication failed'
            }), 400
        
        # Store user in session
        session['user_id'] = user_info['id']
        session['user_name'] = user_info['name']
        session['user_email'] = user_info['email']
        
        # Store user in database
        with get_database_connection(dashboard_api.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (id, email, name, profile_picture, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (
                user_info['id'],
                user_info['email'],
                user_info['name'],
                user_info.get('picture')
            ))
        
        # Clean up session
        session.pop('oauth_state', None)
        
        # Redirect to dashboard with YouTube profile active
        return redirect('/?view=youtube')
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OAuth callback failed: {str(e)}'
        }), 500

@app.route('/auth/logout', methods=['POST'])
def oauth_logout():
    """Logout user and revoke OAuth access."""
    try:
        user_id = session.get('user_id')
        if user_id:
            # Revoke OAuth access
            dashboard_api.oauth_service.revoke_user_access(user_id)
        
        # Clear session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Logout failed: {str(e)}'
        }), 500

@app.route('/api/auth/status')
def auth_status():
    """Get current authentication status."""
    try:
        if 'user_id' not in session:
            return jsonify({
                'authenticated': False,
                'oauth_configured': OAuthConfig.is_configured()
            })
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'name': session.get('user_name'),
                'email': session.get('user_email')
            },
            'oauth_configured': True
        })
        
    except Exception as e:
        return jsonify({
            'authenticated': False,
            'error': str(e)
        }), 500

@app.route('/api/recommendations')
def get_recommendations():
    try:
        # Pass user_id if authenticated for enhanced personalization
        user_id = session.get('user_id')
        recommendations = dashboard_api.get_recommendations(user_id)
        
        formatted_recommendations = []
        for video in recommendations:
            formatted_recommendations.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'confidence': round(video.get('like_probability', 0.5) * 100),
                'views_formatted': format_view_count(video['view_count']),
                'content_similarity': video.get('content_similarity', 0),
                'pattern_boost': video.get('pattern_boost', 1.0)
            })
        
        return jsonify({
            'success': True,
            'videos': formatted_recommendations,
            'model_trained': dashboard_api.model_trained,
            'total_ratings': get_rated_count_from_database(dashboard_api.db_path),
            'personalized': bool(user_id),
            'enhancement_active': bool(user_id and dashboard_api.model_trained)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/rate', methods=['POST'])
def rate_video():
    try:
        data = request.json
        video_id = data.get('video_id')
        liked = data.get('liked')
        
        if not video_id or liked is None:
            return jsonify({
                'success': False,
                'error': 'Missing video_id or liked parameter'
            }), 400
        
        # Save the rating
        save_video_rating_to_database(video_id, liked, "", dashboard_api.db_path)
        
        # Check if we should retrain the model
        model_retrained = False
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        
        if rated_count >= AppConfig.ML_TRAINING_THRESHOLD:  # Minimum ratings needed for training
            # Retrain the model with new data
            if not dashboard_api.model:
                dashboard_api.model = create_recommendation_model()
            
            training_data = get_training_data_from_database(dashboard_api.db_path)
            success = train_model_on_user_preferences(dashboard_api.model, training_data)
            
            if success:
                dashboard_api.model_trained = True
                model_retrained = True
        
        return jsonify({
            'success': True,
            'message': 'Rating saved successfully',
            'model_retrained': model_retrained,
            'total_ratings': rated_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/liked')
def get_liked_videos():
    try:
        liked_videos = dashboard_api.get_liked_videos()
        
        formatted_videos = []
        for video in liked_videos:
            formatted_videos.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'confidence': round(video.get('like_probability', 0.8) * 100),
                'views_formatted': format_view_count(video['view_count'])
            })
        
        return jsonify({
            'success': True,
            'videos': formatted_videos,
            'total_liked': len(formatted_videos)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/remove-liked', methods=['POST'])
def remove_liked_video():
    """Remove a liked video (delete the preference)."""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        # Remove the preference from database
        removed = remove_video_preference(video_id, dashboard_api.db_path)
        
        if not removed:
            return jsonify({
                'success': False,
                'error': 'Video preference not found'
            }), 404
        
        # Check if we should retrain the model
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        model_retrained = False
        
        if rated_count >= AppConfig.ML_TRAINING_THRESHOLD:
            # Retrain the model with updated data
            if not dashboard_api.model:
                dashboard_api.model = create_recommendation_model()
            
            training_data = get_training_data_from_database(dashboard_api.db_path)
            success = train_model_on_user_preferences(dashboard_api.model, training_data)
            if success:
                dashboard_api.model_trained = True
                model_retrained = True
        
        return jsonify({
            'success': True,
            'model_retrained': model_retrained,
            'remaining_rated': rated_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search-topic', methods=['POST'])
def search_topic():
    """Search for videos by topic using AI keyword generation."""
    try:
        data = request.json
        topic = data.get('topic', '').strip()
        
        if not topic:
            return jsonify({
                'success': False,
                'error': 'Topic is required'
            }), 400
        
        # Check if we have a YouTube API key
        import os
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if not youtube_api_key:
            return jsonify({
                'success': False,
                'error': 'YouTube API key not configured'
            }), 500
        
        # Create search session
        session_id = create_search_session(topic, dashboard_api.db_path)
        
        # Initialize the search service
        search_service = TopicVideoSearchService(youtube_api_key, dashboard_api.db_path)
        
        # Test API connection first
        if not search_service.test_api_connection():
            return jsonify({
                'success': False,
                'error': 'YouTube API connection failed. Please check your API key and quota.',
                'session_id': session_id
            }), 500
        
        # Generate keywords using Ollama
        from src.ollama.keyword_generator import generate_keywords_from_topic
        keywords = generate_keywords_from_topic(topic)
        
        if not keywords:
            return jsonify({
                'success': False,
                'error': 'Failed to generate search keywords. Please check if Ollama is running.',
                'session_id': session_id
            }), 500
        
        # Add session metadata to the search service
        # We need to pass the session metadata to the search service so it gets saved with the videos
        session_metadata = {
            'search_session_id': session_id,
            'search_topic': topic
        }
        
        # Search for videos using the generated keywords with session metadata  
        max_queries = 5  # Limit to avoid overwhelming the API
        max_results_per_query = 3  # Conservative per-query limit
        
        videos = search_service.search_and_save_videos(
            queries=keywords[:max_queries],
            max_results_per_query=max_results_per_query,
            session_metadata=session_metadata
        )
        
        # Update search session with video count
        update_search_session_video_count(session_id, len(videos), dashboard_api.db_path)
        
        # Format videos for frontend
        formatted_videos = []
        for video in videos:
            formatted_videos.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'views_formatted': format_view_count(video['view_count']),
                'search_topic': topic,
                'search_session_id': session_id
            })
        
        return jsonify({
            'success': True,
            'videos': formatted_videos,
            'session_id': session_id,
            'topic': topic,
            'keywords_used': keywords,
            'total_videos': len(formatted_videos),
            'message': f'Found {len(formatted_videos)} videos for "{topic}"'
        })
        
    except Exception as e:
        import traceback
        print(f"Search error: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        }), 500

@app.route('/api/add-video-by-url', methods=['POST'])
def add_video_by_url():
    """Add a YouTube video to liked videos by URL or video ID."""
    try:
        data = request.json
        url_or_id = data.get('url', '').strip()
        
        if not url_or_id:
            return jsonify({
                'success': False,
                'error': 'YouTube URL or video ID is required'
            }), 400
        
        # Extract video ID from URL
        video_id = extract_video_id_from_url(url_or_id)
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Invalid YouTube URL or video ID format'
            }), 400
        
        # Check if video already exists in liked videos
        with get_database_connection(dashboard_api.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.title FROM videos v
                JOIN preferences p ON v.id = p.video_id
                WHERE v.id = ? AND p.liked = 1
            ''', (video_id,))
            existing = cursor.fetchone()
            
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Video already in your liked videos: "{existing[0]}"'
                }), 409
        
        # Get YouTube API key
        import os
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if not youtube_api_key:
            return jsonify({
                'success': False,
                'error': 'YouTube API key not configured'
            }), 500
        
        # Initialize YouTube client
        from src.services.youtube_client import YouTubeAPIClient
        youtube_client = YouTubeAPIClient(youtube_api_key)
        
        # Fetch video details
        videos = youtube_client.get_video_details([video_id])
        
        if not videos:
            return jsonify({
                'success': False,
                'error': 'Video not found or could not fetch details. Check if the video exists and is public.'
            }), 404
        
        video = videos[0]
        
        # Save video to database
        from src.database.video_operations import save_videos_to_database, save_video_features_to_database
        save_videos_to_database([video], dashboard_api.db_path)
        
        # Extract and save features
        from src.ml.feature_extraction import extract_all_features_from_video
        features = extract_all_features_from_video(video)
        save_video_features_to_database(video['id'], features, dashboard_api.db_path)
        
        # Add to liked videos
        save_video_rating_to_database(video['id'], True, "Manually added via dashboard", dashboard_api.db_path)
        
        # Retrain model if threshold is met
        model_retrained = False
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        
        if rated_count >= AppConfig.ML_TRAINING_THRESHOLD:
            if not dashboard_api.model:
                dashboard_api.model = create_recommendation_model()
            
            training_data = get_training_data_from_database(dashboard_api.db_path)
            success = train_model_on_user_preferences(dashboard_api.model, training_data)
            
            if success:
                dashboard_api.model_trained = True
                model_retrained = True
        
        return jsonify({
            'success': True,
            'message': f'Successfully added "{video["title"]}" to your liked videos',
            'video': {
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url']
            },
            'model_retrained': model_retrained,
            'total_liked': rated_count
        })
        
    except Exception as e:
        import traceback
        print(f"Error adding video: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to add video: {str(e)}'
        }), 500

def extract_video_id_from_url(url_or_id):
    """Extract YouTube video ID from various URL formats."""
    import re
    
    # If it's already just a video ID (11 characters)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Regular YouTube watch URL
    match = re.search(r'(?:youtube\.com/watch\?v=|youtube\.com/watch\?.*&v=)([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    # Short YouTube URL
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    # YouTube embed URL
    match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    # YouTube video URL with timestamp
    match = re.search(r'youtube\.com/v/([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    return None

@app.route('/api/search-history')
def get_search_history():
    """Get recent search sessions with metadata."""
    try:
        # Get recent search sessions
        sessions = get_recent_search_sessions(20, dashboard_api.db_path)
        
        # Get search statistics
        stats = get_search_sessions_stats(dashboard_api.db_path)
        
        # Format sessions with additional metadata
        formatted_sessions = []
        for session in sessions:
            # Calculate time ago
            from datetime import datetime
            created_at = datetime.fromisoformat(session['created_at'])
            time_ago = get_time_ago(created_at)
            
            formatted_sessions.append({
                'id': session['id'],
                'topic': session['topic'],
                'video_count': session['video_count'],
                'created_at': session['created_at'],
                'time_ago': time_ago,
                'status': session['status']
            })
        
        return jsonify({
            'success': True,
            'sessions': formatted_sessions,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search-session/<session_id>')
def get_search_session_videos(session_id):
    """Get videos from a specific search session."""
    try:
        videos = get_videos_by_search_session(session_id, dashboard_api.db_path)
        
        formatted_videos = []
        for video in videos:
            formatted_videos.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'views_formatted': format_view_count(video['view_count']),
                'search_topic': video.get('search_topic', 'Unknown')
            })
        
        return jsonify({
            'success': True,
            'videos': formatted_videos,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cleanup-searches', methods=['POST'])
def cleanup_searches():
    """Clean up old search sessions."""
    try:
        data = request.json or {}
        days_old = data.get('days_old', 7)
        
        cleaned_count = cleanup_old_search_sessions(days_old, dashboard_api.db_path)
        
        # Get updated stats
        stats = get_search_sessions_stats(dashboard_api.db_path)
        
        return jsonify({
            'success': True,
            'cleaned_sessions': cleaned_count,
            'message': f'Archived {cleaned_count} old search sessions',
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/delete-search-session/<session_id>', methods=['DELETE'])
def delete_search_session_endpoint(session_id):
    """Delete a specific search session."""
    try:
        data = request.json or {}
        remove_videos = data.get('remove_videos', False)
        
        success = delete_search_session(session_id, dashboard_api.db_path, remove_videos)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Search session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Search session deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_time_ago(datetime_obj):
    """Convert datetime to human-readable time ago string."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    diff = now - datetime_obj
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def format_view_count(count):
    if count >= 1000000:
        return f"{count/1000000:.1f}M views"
    elif count >= 1000:
        return f"{count/1000:.1f}K views"
    else:
        return f"{count} views"

# YouTube profile API endpoints
@app.route('/api/youtube/profile')
@oauth_required
def get_youtube_profile():
    """Get user's YouTube profile and data."""
    try:
        user_id = session['user_id']
        
        # Try cached data first
        user_data = dashboard_api.youtube_user_service.get_cached_user_data(user_id)
        
        if not user_data:
            # Fetch fresh data
            user_data = dashboard_api.youtube_user_service.get_user_youtube_data(user_id)
        
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Unable to fetch YouTube data. Please check your OAuth permissions.',
                'suggestions': [
                    'Ensure you granted YouTube read access during login',
                    'Try logging out and logging in again',
                    'Check if your YouTube account has any content restrictions'
                ]
            }), 400
        
        # Format response for frontend
        response_data = {
            'success': True,
            'profile': {
                'channel': user_data['channel_info'],
                'stats': {
                    'liked_videos': len(user_data.get('liked_videos', [])),
                    'subscriptions': len(user_data.get('subscriptions', [])),
                    'activities': len(user_data.get('activities', []))
                }
            },
            'liked_videos': user_data.get('liked_videos', []),  # All available videos for pagination
            'subscriptions': user_data.get('subscriptions', [])[:20],  # First 20 for preview
            'recent_activities': user_data.get('activities', [])[:10]  # First 10 for preview
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch YouTube profile: {str(e)}'
        }), 500

@app.route('/api/youtube/sync', methods=['POST'])
@oauth_required
def sync_youtube_data():
    """Force refresh of user's YouTube data."""
    try:
        user_id = session['user_id']
        
        # Fetch fresh data
        user_data = dashboard_api.youtube_user_service.get_user_youtube_data(user_id)
        
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Failed to sync YouTube data. Check your OAuth permissions.'
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'YouTube data synced successfully',
            'stats': {
                'liked_videos': len(user_data.get('liked_videos', [])),
                'subscriptions': len(user_data.get('subscriptions', [])),
                'activities': len(user_data.get('activities', []))
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to sync YouTube data: {str(e)}'
        }), 500

@app.route('/api/youtube/personalization-preview')
@oauth_required
def get_personalization_preview():
    """Get preview of how YouTube data will enhance personalization."""
    try:
        user_id = session['user_id']
        
        # Get personalization tags from YouTube data
        tags = dashboard_api.youtube_user_service.get_youtube_tags_for_personalization(user_id)
        
        # Get current recommendation stats
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        
        return jsonify({
            'success': True,
            'personalization': {
                'youtube_tags': tags[:50],  # First 50 tags
                'total_tags': len(tags),
                'current_ratings': rated_count,
                'enhancement_potential': 'high' if len(tags) > 20 else 'moderate' if len(tags) > 5 else 'low',
                'description': f'Found {len(tags)} personalization tags from your YouTube activity'
            },
            'recommendations': {
                'before': 'Based on manual ratings only',
                'after': 'Enhanced with YouTube history patterns'
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to generate personalization preview: {str(e)}'
        }), 500

@app.route('/api/youtube/personalization-stats')
@oauth_required
def get_personalization_stats():
    """Get detailed personalization statistics."""
    try:
        user_id = session['user_id']
        
        stats = dashboard_api.personalized_service.get_personalization_stats(user_id)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get personalization stats: {str(e)}'
        }), 500

@app.route('/api/import-youtube-video', methods=['POST'])
@oauth_required
def import_youtube_video():
    """Import a video from user's YouTube profile to MyTube collection."""
    try:
        data = request.json
        video_id = data.get('video_id')
        user_id = session['user_id']
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        # Get user's YouTube data to find the video details
        user_data = dashboard_api.youtube_user_service.get_cached_user_data(user_id)
        if not user_data:
            user_data = dashboard_api.youtube_user_service.get_user_youtube_data(user_id)
        
        if not user_data:
            return jsonify({
                'success': False,
                'error': 'Unable to access YouTube data. Please sync your profile first.'
            }), 400
        
        # Find the video in the user's liked videos
        youtube_video = None
        for video in user_data.get('liked_videos', []):
            if video.get('id') == video_id:
                youtube_video = video
                break
        
        if not youtube_video:
            return jsonify({
                'success': False,
                'error': 'Video not found in your YouTube liked videos'
            }), 404
        
        # Check if video already exists in MyTube
        with get_database_connection(dashboard_api.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.title FROM videos v
                JOIN preferences p ON v.id = p.video_id
                WHERE v.id = ? AND p.liked = 1
            ''', (video_id,))
            existing = cursor.fetchone()
            
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Video already in your MyTube collection: "{existing[0]}"'
                }), 409
        
        # Create video record from YouTube data
        video_record = {
            'id': youtube_video['id'],
            'title': youtube_video['title'],
            'description': youtube_video.get('description', ''),
            'channel_name': youtube_video['channel_name'],
            'view_count': youtube_video.get('view_count', 0),
            'like_count': youtube_video.get('like_count', 0),
            'comment_count': 0,  # Not available in YouTube liked videos API
            'duration': youtube_video.get('duration', ''),
            'published_at': youtube_video.get('published_at', ''),
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            'tags': ','.join(youtube_video.get('tags', [])),
            'category_id': 28,  # Science & Technology default
            'url': f"https://www.youtube.com/watch?v={video_id}"
        }
        
        # Save video to database
        from src.database.video_operations import save_videos_to_database, save_video_features_to_database
        save_videos_to_database([video_record], dashboard_api.db_path)
        
        # Extract and save features
        from src.ml.feature_extraction import extract_all_features_from_video
        features = extract_all_features_from_video(video_record)
        save_video_features_to_database(video_record['id'], features, dashboard_api.db_path)
        
        # Add to MyTube (liked videos)
        save_video_rating_to_database(video_record['id'], True, "Imported from YouTube profile", dashboard_api.db_path)
        
        # Check if we should retrain the model
        model_retrained = False
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        
        if rated_count >= AppConfig.ML_TRAINING_THRESHOLD:
            if not dashboard_api.model:
                dashboard_api.model = create_recommendation_model()
            
            training_data = get_training_data_from_database(dashboard_api.db_path)
            success = train_model_on_user_preferences(dashboard_api.model, training_data)
            
            if success:
                dashboard_api.model_trained = True
                model_retrained = True
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported "{video_record["title"]}" to MyTube',
            'video': {
                'id': video_record['id'],
                'title': video_record['title'],
                'channel_name': video_record['channel_name'],
                'view_count': video_record['view_count']
            },
            'model_retrained': model_retrained,
            'total_mytubes': rated_count
        })
        
    except Exception as e:
        import traceback
        print(f"Error importing YouTube video: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to import video: {str(e)}'
        }), 500

@app.route('/api/video-tags/<video_id>')
def get_video_tags(video_id):
    """Get tags and metadata for a specific video for similarity search."""
    try:
        with get_database_connection(dashboard_api.db_path) as conn:
            cursor = conn.cursor()
            
            # Get video details and tags
            cursor.execute('''
                SELECT v.id, v.title, v.description, v.channel_name, v.tags, v.category_id
                FROM videos v
                JOIN preferences p ON v.id = p.video_id
                WHERE v.id = ? AND p.liked = 1
            ''', (video_id,))
            
            video_row = cursor.fetchone()
            if not video_row:
                return jsonify({
                    'success': False,
                    'error': 'Video not found in MyTube collection'
                }), 404
            
            video_data = {
                'id': video_row[0],
                'title': video_row[1],
                'description': video_row[2] or '',
                'channel_name': video_row[3],
                'tags': video_row[4] or '',
                'category_id': video_row[5]
            }
            
            # Parse tags from the stored string
            tags_list = []
            if video_data['tags']:
                tags_list = [tag.strip() for tag in video_data['tags'].split(',') if tag.strip()]
            
            # If no tags from video metadata, extract keywords from title and description
            if not tags_list:
                text_to_analyze = f"{video_data['title']} {video_data['description']}"
                
                # Extract potential keywords using simple text analysis
                import re
                # Remove common words and extract meaningful keywords
                common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'this', 'that', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
                
                # Extract words and clean them
                words = re.findall(r'\b[a-zA-Z]{3,}\b', text_to_analyze.lower())
                tags_list = [word for word in words if word not in common_words][:10]
            
            return jsonify({
                'success': True,
                'video': {
                    'id': video_data['id'],
                    'title': video_data['title'],
                    'channel_name': video_data['channel_name']
                },
                'tags': tags_list[:10],  # Limit to first 10 tags
                'total_tags': len(tags_list)
            })
            
    except Exception as e:
        import traceback
        print(f"Error getting video tags: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to get video tags: {str(e)}'
        }), 500

@app.route('/api/find-similar-videos', methods=['POST'])
def find_similar_videos():
    """Find videos similar to a liked video using its tags."""
    try:
        data = request.json
        video_id = data.get('video_id')
        search_topic = data.get('search_topic')
        
        if not video_id:
            return jsonify({
                'success': False,
                'error': 'video_id is required'
            }), 400
        
        if not search_topic:
            return jsonify({
                'success': False,
                'error': 'search_topic is required'
            }), 400
        
        # Get YouTube API key
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if not youtube_api_key:
            return jsonify({
                'success': False,
                'error': 'YouTube API key not configured'
            }), 500
        
        # Create a new search session for this similarity search
        session_id = create_search_session(f"Similar to video {video_id}", dashboard_api.db_path)
        
        # Initialize the search service
        search_service = TopicVideoSearchService(youtube_api_key, dashboard_api.db_path)
        
        # Test API connection first
        if not search_service.test_api_connection():
            return jsonify({
                'success': False,
                'error': 'YouTube API connection failed. Please check your API key and quota.',
                'session_id': session_id
            }), 500
        
        # Generate keywords using Ollama from the search topic (which is made from video tags)
        from src.ollama.keyword_generator import generate_keywords_from_topic
        keywords = generate_keywords_from_topic(search_topic)
        
        if not keywords:
            # Fallback: use the search topic directly as keywords
            keywords = search_topic.split()
        
        # Add session metadata
        session_metadata = {
            'search_session_id': session_id,
            'search_topic': search_topic
        }
        
        # Search for videos using the generated keywords with session metadata  
        max_queries = 3  # Limit to avoid overwhelming the API for similarity search
        max_results_per_query = 5  # Get more results for better similarity matching
        
        videos = search_service.search_and_save_videos(
            queries=keywords[:max_queries],
            max_results_per_query=max_results_per_query,
            session_metadata=session_metadata
        )
        
        if not videos:
            return jsonify({
                'success': False,
                'error': 'No similar videos found for this topic'
            }), 404
        
        # Update search session with video count
        update_search_session_video_count(session_id, len(videos), dashboard_api.db_path)
        
        # Format videos for response (same as topic search endpoint)
        formatted_videos = []
        for video in videos:
            formatted_videos.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'views_formatted': format_view_count(video['view_count']),
                'search_topic': search_topic
            })
        
        # Filter out the original video from results if it appears
        similar_videos = [v for v in formatted_videos if v['id'] != video_id]
        
        return jsonify({
            'success': True,
            'videos': similar_videos,
            'session_id': session_id,
            'total_found': len(similar_videos),
            'search_topic': search_topic,
            'original_video_id': video_id,
            'keywords_used': keywords[:max_queries]
        })
        
    except Exception as e:
        import traceback
        print(f"Error finding similar videos: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to find similar videos: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Use HTTPS for OAuth compliance
    app.run(debug=True, port=5001, host='localhost', ssl_context='adhoc')