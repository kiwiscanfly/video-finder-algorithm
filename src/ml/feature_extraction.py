from typing import Dict, Tuple

def calculate_basic_video_metrics(video: Dict) -> Tuple:
    title_length = len(video['title'])
    description_length = len(video['description'])
    view_like_ratio = video['like_count'] / max(video['view_count'], 1)
    engagement_score = (video['like_count'] + video['comment_count']) / max(video['view_count'], 1)

    return (title_length, description_length, view_like_ratio, engagement_score)

def detect_keyword_features_in_video(title: str, description: str) -> Tuple:
    tutorial_keywords = ['tutorial', 'learn', 'course', 'guide', 'how to']
    time_keywords = ['24 hours', '1 day', '1 hour', 'minutes', 'seconds', 'crash course']
    beginner_keywords = ['beginner', 'start', 'basics', 'introduction', 'getting started']
    ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'neural network']
    challenge_keywords = ['challenge', 'build', 'create', 'project', 'coding']

    has_tutorial = any(kw in title or kw in description for kw in tutorial_keywords)
    has_time_constraint = any(kw in title for kw in time_keywords)
    has_beginner = any(kw in title or kw in description for kw in beginner_keywords)
    has_ai = any(kw in title or kw in description for kw in ai_keywords)
    has_challenge = any(kw in title for kw in challenge_keywords)

    return (has_tutorial, has_time_constraint, has_beginner, has_ai, has_challenge)

def calculate_title_sentiment_score(title: str) -> float:
    positive_words = ['amazing', 'best', 'awesome', 'great', 'perfect', 'love', 'incredible']
    negative_words = ['hard', 'difficult', 'impossible', 'failed', 'broke', 'wrong']

    positive_count = sum(1 for word in positive_words if word in title)
    negative_count = sum(1 for word in negative_words if word in title)
    return positive_count - negative_count

def extract_all_features_from_video(video: Dict) -> Tuple:
    title = video['title'].lower()
    description = video['description'].lower()

    basic_metrics = calculate_basic_video_metrics(video)
    keyword_features = detect_keyword_features_in_video(title, description)
    sentiment_score = calculate_title_sentiment_score(title)

    return basic_metrics + keyword_features + (sentiment_score,)