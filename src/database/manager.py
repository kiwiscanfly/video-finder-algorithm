import sqlite3
from datetime import datetime
from typing import List, Dict

def setup_database_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            view_count INTEGER,
            like_count INTEGER,
            comment_count INTEGER,
            duration TEXT,
            published_at TEXT,
            channel_name TEXT,
            thumbnail_url TEXT,
            tags TEXT,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            liked BOOLEAN,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_features (
            video_id TEXT PRIMARY KEY,
            title_length INTEGER,
            description_length INTEGER,
            view_like_ratio REAL,
            engagement_score REAL,
            title_sentiment REAL,
            has_tutorial_keywords BOOLEAN,
            has_time_constraint BOOLEAN,
            has_beginner_keywords BOOLEAN,
            has_ai_keywords BOOLEAN,
            has_challenge_keywords BOOLEAN,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_sessions (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            video_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    ''')

    # OAuth and user data tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            profile_picture TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_uri TEXT,
            client_id TEXT,
            client_secret TEXT,
            scopes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, provider)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS youtube_user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            youtube_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id)
        )
    ''')

    # Add search_session_id column to videos table if it doesn't exist
    cursor.execute("PRAGMA table_info(videos)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'search_session_id' not in columns:
        cursor.execute('ALTER TABLE videos ADD COLUMN search_session_id TEXT')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_search_session ON videos(search_session_id)')

    # Add search_topic column to videos table if it doesn't exist  
    if 'search_topic' not in columns:
        cursor.execute('ALTER TABLE videos ADD COLUMN search_topic TEXT')

    # Create indexes for OAuth tables
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_id ON oauth_tokens(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_youtube_user_data_user_id ON youtube_user_data(user_id)')

    conn.commit()
    conn.close()