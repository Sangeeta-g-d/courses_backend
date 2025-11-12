# In your views.py or utils.py
from django.db.models import Sum, F
from django.contrib.auth import get_user_model

def get_user_watch_time_rankings():
    """
    Get top users ranked by total watched duration and include current user's rank
    """
    User = get_user_model()
    
    # Get all users with their total watched duration
    users_ranked = User.objects.annotate(
        total_watched_duration=Sum('progress__watched_duration')
    ).filter(
        total_watched_duration__isnull=False
    ).order_by('-total_watched_duration')
    
    return users_ranked

def get_user_rank(user):
    """
    Get specific user's rank based on watched duration
    """
    ranked_users = get_user_watch_time_rankings()
    
    # Find the user's position in the ranked list
    for index, ranked_user in enumerate(ranked_users, start=1):
        if ranked_user.id == user.id:
            return index
    
    return None