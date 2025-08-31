"""
Google OAuth 2.0 service for YouTube Data API access.
Handles authentication flow and token management.
"""

import os
import json
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import google.auth.transport.requests
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.exceptions import RefreshError

from src.config.app_config import OAuthConfig
from src.database.connection import get_database_connection


class OAuthService:
    """
    Service for managing Google OAuth 2.0 authentication for YouTube Data API.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize OAuth service.
        
        Args:
            db_path: Database path for storing user sessions
        """
        self.db_path = db_path
        self.scopes = [
            'https://www.googleapis.com/auth/youtube.readonly',
            'openid', 
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
    
    def get_authorization_url(self, state: str = None) -> tuple[str, str]:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: Optional state parameter for security
            
        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Create OAuth flow
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            OAuthConfig.get_client_config(),
            scopes=self.scopes,
            state=state
        )
        flow.redirect_uri = OAuthConfig.REDIRECT_URI
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )
        
        return authorization_url, state
    
    def handle_authorization_callback(self, authorization_response: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Handle OAuth callback and exchange code for tokens.
        
        Args:
            authorization_response: Full callback URL
            state: State parameter for verification
            
        Returns:
            User info dict if successful, None otherwise
        """
        try:
            # Create OAuth flow
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                OAuthConfig.get_client_config(),
                scopes=self.scopes,
                state=state
            )
            flow.redirect_uri = OAuthConfig.REDIRECT_URI
            
            # Exchange authorization code for tokens
            flow.fetch_token(authorization_response=authorization_response)
            
            # Get credentials
            credentials = flow.credentials
            
            # Get user info
            user_info = self._get_user_info(credentials)
            if not user_info:
                return None
            
            # Store credentials in database
            self._store_user_credentials(user_info['id'], credentials)
            
            return user_info
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return None
    
    def get_user_credentials(self, user_id: str) -> Optional[google.oauth2.credentials.Credentials]:
        """
        Retrieve and refresh user credentials from database.
        
        Args:
            user_id: User ID
            
        Returns:
            Valid credentials or None
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT access_token, refresh_token, token_uri, client_id, client_secret, scopes
                    FROM oauth_tokens 
                    WHERE user_id = ? AND provider = 'google'
                ''', (user_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Create credentials object
                credentials = google.oauth2.credentials.Credentials(
                    token=row[0],
                    refresh_token=row[1],
                    token_uri=row[2],
                    client_id=row[3],
                    client_secret=row[4],
                    scopes=json.loads(row[5])
                )
                
                # Check if token needs refresh
                if credentials.expired:
                    request = google.auth.transport.requests.Request()
                    credentials.refresh(request)
                    
                    # Update token in database
                    self._update_access_token(user_id, credentials.token)
                
                return credentials
                
        except RefreshError:
            # Refresh token expired, remove from database
            self._remove_user_credentials(user_id)
            return None
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None
    
    def revoke_user_access(self, user_id: str) -> bool:
        """
        Revoke user's OAuth access and remove credentials.
        
        Args:
            user_id: User ID
            
        Returns:
            Success status
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if credentials:
                # Revoke token with Google
                revoke_request = google.auth.transport.requests.Request()
                google.oauth2.credentials.revoke(credentials.token, revoke_request)
            
            # Remove from database
            self._remove_user_credentials(user_id)
            return True
            
        except Exception as e:
            print(f"Error revoking access: {e}")
            return False
    
    def _get_user_info(self, credentials: google.oauth2.credentials.Credentials) -> Optional[Dict[str, Any]]:
        """
        Get user information from Google.
        
        Args:
            credentials: Valid OAuth credentials
            
        Returns:
            User info dict
        """
        try:
            # Build OAuth2 service
            oauth2_service = googleapiclient.discovery.build(
                'oauth2', 'v2', credentials=credentials
            )
            
            user_info = oauth2_service.userinfo().get().execute()
            return user_info
            
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None
    
    def _store_user_credentials(self, user_id: str, credentials: google.oauth2.credentials.Credentials):
        """
        Store user credentials in database.
        
        Args:
            user_id: User ID
            credentials: OAuth credentials
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Store/update credentials
                cursor.execute('''
                    INSERT OR REPLACE INTO oauth_tokens 
                    (user_id, provider, access_token, refresh_token, token_uri, client_id, client_secret, scopes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    user_id,
                    'google',
                    credentials.token,
                    credentials.refresh_token,
                    credentials.token_uri,
                    credentials.client_id,
                    credentials.client_secret,
                    json.dumps(credentials.scopes)
                ))
                
        except Exception as e:
            print(f"Error storing credentials: {e}")
    
    def _update_access_token(self, user_id: str, access_token: str):
        """
        Update access token in database.
        
        Args:
            user_id: User ID
            access_token: New access token
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE oauth_tokens 
                    SET access_token = ?, updated_at = datetime('now')
                    WHERE user_id = ? AND provider = 'google'
                ''', (access_token, user_id))
                
        except Exception as e:
            print(f"Error updating access token: {e}")
    
    def _remove_user_credentials(self, user_id: str):
        """
        Remove user credentials from database.
        
        Args:
            user_id: User ID
        """
        try:
            with get_database_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM oauth_tokens 
                    WHERE user_id = ? AND provider = 'google'
                ''', (user_id,))
                
        except Exception as e:
            print(f"Error removing credentials: {e}")