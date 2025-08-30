import sqlite3
import pandas as pd

from src.database.connection import get_database_connection

def save_video_rating_to_database(video_id: str, liked: bool, notes: str, db_path: str):
    """Save video rating to database using context manager for safe connection handling."""
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO preferences (video_id, liked, notes) VALUES (?, ?, ?)
        ''', (video_id, liked, notes))

def get_training_data_from_database(db_path: str) -> pd.DataFrame:
    """Get training data from database using context manager for safe connection handling."""
    with get_database_connection(db_path) as conn:
        query = '''
            SELECT vf.*, p.liked
            FROM video_features vf
            JOIN preferences p ON vf.video_id = p.video_id
        '''
        df = pd.read_sql_query(query, conn)
        return df

def get_unrated_videos_with_features_from_database(db_path: str) -> pd.DataFrame:
    """Get unrated videos with features from database using context manager for safe connection handling."""
    with get_database_connection(db_path) as conn:
        query = '''
            SELECT v.*, vf.*
            FROM videos v
            JOIN video_features vf ON v.id = vf.video_id
            LEFT JOIN preferences p ON v.id = p.video_id
            WHERE p.video_id IS NULL
            ORDER BY v.view_count DESC
        '''
        df = pd.read_sql_query(query, conn)
        return df

def get_rated_count_from_database(db_path: str) -> int:
    """Get count of rated videos from database using context manager for safe connection handling."""
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM preferences")
        count = cursor.fetchone()[0]
        return count