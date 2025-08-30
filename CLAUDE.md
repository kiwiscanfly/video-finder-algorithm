# Video Inspiration Finder - Project Overview

## Project Purpose
An intelligent YouTube video recommendation system that learns user preferences through machine learning to suggest coding videos. Features both CLI and web dashboard interfaces.

## Core Architecture

### 1. Data Flow
```
YouTube API → Search/Fetch Videos → SQLite Database → Feature Extraction → ML Model → Recommendations → User Interface
```

### 2. Key Components

#### YouTube Integration (`src/youtube/`)
- **search.py**: Searches YouTube for coding videos using predefined queries
  - Current queries: "coding experiment", "machine learning", "data science", "learning vim", "neovim setup"
  - Filters: Category 28 (Science & Technology), published after 2020
- **details.py**: Fetches detailed video metadata
- **utils.py**: Helper functions (duplicate removal)

#### Database Layer (`src/database/`)
- **manager.py**: SQLite schema setup
- **video_operations.py**: CRUD operations for videos
- **preference_operations.py**: User ratings management
- Tables: videos, video_features, preferences

#### Machine Learning (`src/ml/`)
- **feature_extraction.py**: Extracts 11 features from videos:
  - Content: title length, description length, keywords
  - Engagement: view count, like ratio, engagement score
  - Semantic: sentiment, tutorial/beginner/AI keywords
  - Behavioral: time constraints, challenge keywords
- **model_training.py**: RandomForest classifier (100 trees)
- **predictions.py**: Generates confidence scores (0-100%)

#### User Interfaces
- **CLI Mode** (`main.py`, `src/rating/`): Interactive terminal rating system
- **Web Dashboard** (`dashboard_api.py`, `templates/dashboard.html`): 
  - Flask API on port 5001
  - YouTube-like grid layout
  - Real-time rating with visual feedback
  - Shows AI confidence scores

### 3. ML Learning Process
1. **Cold Start**: Random videos until 10+ ratings
2. **Model Training**: Activates after 10 ratings
3. **Continuous Learning**: Retrains after each new rating
4. **Predictions**: Sorts videos by confidence score

## Entry Points

### Main Scripts
- `setup.sh`: Automated setup (venv, dependencies, menu)
- `main.py`: CLI application
- `dashboard_api.py`: Web server
- `run_dashboard.py`: Dashboard launcher
- `search_more_videos.py`: Additional video search

### Setup Options
1. **Dashboard Only**: Launch web interface
2. **CLI Mode**: Terminal-based rating
3. **Search Videos**: Populate database
4. **Full Setup**: Search + Rate + Dashboard

## Configuration

### Environment Variables
- `YOUTUBE_API_KEY`: Required for YouTube API access
- Located in `.env` file

### Dependencies
- Core: requests, pandas, scikit-learn, numpy
- Web: flask, flask-cors
- Database: sqlite3 (built-in)
- Utilities: python-dotenv

## Database Schema

### videos table
- id, title, channel_name, view_count, url, etc.

### video_features table
- video_id, title_length, description_length
- view_like_ratio, engagement_score, title_sentiment
- has_tutorial_keywords, has_beginner_keywords, etc.

### preferences table
- video_id, liked (boolean), notes, created_at

## API Endpoints

### Dashboard API (port 5001)
- `GET /`: Serve dashboard HTML
- `GET /api/recommendations`: Get video recommendations
- `POST /api/rate`: Submit video rating
- `GET /api/liked`: Get liked videos

## Current Status
- Database: video_inspiration.db
- Search queries configured: 5 queries
- Model threshold: 10 ratings minimum
- Dashboard URL: http://localhost:5001

## Quick Commands
```bash
# Full setup
./setup.sh

# Direct commands
python3 main.py                    # CLI mode
python3 dashboard_api.py           # Web dashboard
python3 search_more_videos.py      # Search more videos
```

## Notes
- All data stored locally in SQLite
- No external tracking or data sharing
- Model uses RandomForest with 100 estimators
- Videos filtered to Science & Technology category
- Published after 2020 for relevance