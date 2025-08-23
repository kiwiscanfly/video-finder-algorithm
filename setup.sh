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
pip install requests pandas scikit-learn numpy python-dotenv

echo "✅ Setup complete!"
echo "🚀 Running Video Inspiration Finder..."

# Run the main script
python main.py