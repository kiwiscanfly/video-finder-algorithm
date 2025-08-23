from typing import Dict

def display_video_information_for_rating(video: Dict):
    print(f"\n{'='*50}")
    print(f"Title: {video['title']}")
    print(f"Channel: {video['channel_name']}")
    print(f"Views: {video['view_count']:,}")
    print(f"URL: {video['url']}")
    print(f"{'='*50}")

def display_rating_session_header():
    print("🎯 Video Inspiration Finder - Interactive Session")
    print("Rate videos with 'y' (like), 'n' (dislike), 'q' (quit)")

def display_session_type_message(is_ml_ready: bool, rated_count: int) -> str:
    if is_ml_ready:
        return "📊 ML Recommendations based on your preferences:"
    else:
        remaining_needed = max(0, 10 - rated_count)
        if remaining_needed == 0:
            return "🎓 Ready to train ML model!"
        return f"📹 Unrated videos (need {remaining_needed} more to train ML):"