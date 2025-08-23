#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from pathlib import Path

def check_database_exists():
    return Path("video_inspiration.db").exists()

def check_has_videos():
    if not check_database_exists():
        return False
    
    import sqlite3
    try:
        conn = sqlite3.connect("video_inspiration.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM videos")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False

def main():
    print("🚀 Video Inspiration Dashboard")
    print("=" * 40)
    
    # Check if database and videos exist
    if not check_has_videos():
        print("⚠️  No videos found in database!")
        print("\nOptions:")
        print("1. Run main application first to search and rate videos")
        print("2. Continue with empty dashboard (demo mode)")
        
        choice = input("\nEnter choice (1/2): ").strip()
        
        if choice == "1":
            print("\n🔍 Running main application first...")
            try:
                subprocess.run([sys.executable, "main.py"], check=True)
            except KeyboardInterrupt:
                print("\n👋 Switching to dashboard...")
                time.sleep(1)
            except Exception as e:
                print(f"Error running main app: {e}")
                return
    
    # Start dashboard
    print("\n🌐 Starting dashboard server...")
    print("📱 Dashboard will be available at: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        subprocess.run([sys.executable, "dashboard_api.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped!")
    except Exception as e:
        print(f"Error starting dashboard: {e}")

if __name__ == "__main__":
    main()