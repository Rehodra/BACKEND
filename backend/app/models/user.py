USER_COLLECTION = "users"

def user_dict(email: str, name: str, user_name: str = None, google_id: str = None, picture: str = None):
    return {
        "email": email,
        "name": name,
        "user_name": user_name,
        "google_id": google_id,
        "picture": picture
    }

