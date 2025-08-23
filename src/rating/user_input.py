def get_user_rating_response() -> str:
    while True:
        response = input("Rate this video (y/n/q): ").strip().lower()
        if response in ['y', 'n', 'q']:
            return response
        print("Please enter 'y', 'n', or 'q'")

def get_user_notes_for_rating(liked: bool) -> str:
    if liked:
        return input("Why did you like it? (optional): ").strip()
    else:
        return input("Why didn't you like it? (optional): ").strip()