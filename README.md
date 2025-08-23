# Video Inspiration Finder 🎯

AI-powered YouTube video recommendation system that learns your preferences to suggest coding videos you'll love.

## Features

- 🔍 **Smart Search**: Finds viral coding videos from YouTube
- 🤖 **Machine Learning**: RandomForest model learns your preferences  
- 📊 **Web Dashboard**: YouTube-like interface showing personalized recommendations
- 🔒 **Privacy First**: All data stored locally in SQLite
- ⚡ **Fast Setup**: One command installation and execution

## Quick Start

### Option 1: Command Line Interface
```bash
./setup.sh
```
This will:
1. Create virtual environment
2. Install dependencies  
3. Search for videos
4. Start interactive rating session

### Option 2: Web Dashboard
```bash
./setup.sh  # First time setup
python run_dashboard.py
```
Opens a YouTube-like dashboard at `http://localhost:5000`

## How It Works

1. **Search Phase**: Queries YouTube API for trending coding videos
2. **Rating Phase**: You rate videos as like/dislike with optional notes
3. **Learning Phase**: After 10+ ratings, ML model activates
4. **Recommendation Phase**: AI suggests videos based on your preferences

## Project Structure

```
src/
├── database/     # SQLite operations
├── youtube/      # YouTube API integration  
├── ml/          # Machine learning pipeline
└── rating/      # Interactive rating system

main.py           # CLI application
dashboard_api.py  # Web API server
templates/        # Dashboard HTML/CSS/JS
```

## ML Pipeline

- **Features**: 11 extracted features (keywords, engagement, sentiment)
- **Model**: RandomForest with 100 trees
- **Training**: Incremental learning after each rating
- **Prediction**: Confidence scores for video recommendations

## Requirements

- Python 3.7+
- YouTube Data API v3 key
- SQLite (included with Python)

## Setup

1. Get YouTube API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Create `.env` file:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```
3. Run `./setup.sh`

## Dashboard Features

- 📱 Responsive YouTube-like design
- 🎯 AI confidence scores for each recommendation
- 🔄 Real-time model status (learning vs trained)
- 🖱️ Click videos to open in YouTube
- 📊 Visual feedback on model training progress

## Commands

```bash
./setup.sh              # Full setup and CLI
python main.py           # CLI only
python run_dashboard.py  # Web dashboard
python dashboard_api.py  # API server only
```

Built with Python, Flask, scikit-learn, and YouTube Data API v3.