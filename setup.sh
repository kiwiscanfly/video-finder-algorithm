#!/bin/bash

echo "🔧 Setting up Video Inspiration Finder..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install requests pandas scikit-learn numpy python-dotenv flask flask-cors

echo "✅ Setup complete!"

# Function to check if database has videos
check_videos() {
    if [ -f "video_inspiration.db" ]; then
        video_count=$(sqlite3 video_inspiration.db "SELECT COUNT(*) FROM videos;" 2>/dev/null || echo "0")
        echo $video_count
    else
        echo "0"
    fi
}

# Function to check unrated videos count
check_unrated_videos() {
    if [ -f "video_inspiration.db" ]; then
        unrated_count=$(sqlite3 video_inspiration.db "SELECT COUNT(*) FROM videos v LEFT JOIN preferences p ON v.id = p.video_id WHERE p.video_id IS NULL;" 2>/dev/null || echo "0")
        echo $unrated_count
    else
        echo "0"
    fi
}

# Check current state
video_count=$(check_videos)
unrated_count=$(check_unrated_videos)

echo ""
echo "📊 Current Status:"
echo "   Total videos: $video_count"
echo "   Unrated videos: $unrated_count"
echo ""

# Main menu
echo "Choose what you want to do:"
echo "1. 🌐 Launch Dashboard (recommended)"
echo "2. 📱 Interactive CLI Rating Session"  
echo "3. 🔍 Search for More Videos"
echo "4. 🛠️ Full Setup (Search + Rate + Dashboard)"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🌐 Launching Dashboard..."
        if [ "$unrated_count" -eq "0" ] && [ "$video_count" -gt "0" ]; then
            echo "⚠️  All videos are rated. Searching for more videos first..."
            python search_more_videos.py
        elif [ "$video_count" -eq "0" ]; then
            echo "⚠️  No videos found. Searching for videos first..."
            python main.py --search-only 2>/dev/null || python search_more_videos.py
        fi
        echo ""
        echo "📱 Dashboard will be available at: http://localhost:5001"
        echo "🛑 Press Ctrl+C to stop the server"
        echo "----------------------------------------"
        python dashboard_api.py
        ;;
    2)
        echo ""
        echo "📱 Starting Interactive Rating Session..."
        python main.py
        ;;
    3)
        echo ""
        echo "🔍 Searching for more videos..."
        python search_more_videos.py
        echo ""
        echo "✅ Search complete! You can now:"
        echo "   • Run './setup.sh' again and choose option 1 for Dashboard"
        echo "   • Run 'python dashboard_api.py' directly"
        ;;
    4)
        echo ""
        echo "🛠️  Running Full Setup..."
        echo "🔍 Step 1: Searching for videos..."
        python main.py --search-only 2>/dev/null || python search_more_videos.py
        echo ""
        echo "📱 Step 2: Starting rating session..."
        echo "💡 Tip: Rate at least 10 videos to activate AI recommendations"
        echo "   (You can press 'q' anytime to skip to dashboard)"
        python main.py
        ;;
    *)
        echo "❌ Invalid choice. Please run './setup.sh' again."
        exit 1
        ;;
esac