from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model
from admin_part.models import UserProgress, Enrollment

User = get_user_model()


def get_user_watch_time_rankings():
    """
    Rank users by:
    1. Completed courses (DESC)
    2. Total watch time (DESC)
    """

    users = User.objects.annotate(
        completed_courses=Count(
            'enrollments',
            filter=Q(enrollments__progress_percentage=100),
            distinct=True
        ),
        total_watch_time=Sum(
            'progress__watched_duration'
        )
    ).filter(
        total_watch_time__isnull=False
    ).order_by(
        '-completed_courses',
        '-total_watch_time'
    )

    ranking = []
    rank = 1

    for user in users:
        ranking.append({
            "rank": rank,
            "user_id": user.id,
            "name": user.get_full_name() or user.username,
            "completed_courses": user.completed_courses,
            "total_watch_time_minutes": int((user.total_watch_time or 0) / 60),
        })
        rank += 1

    return ranking


def get_user_rank(user):
    """
    Returns rank of a specific user
    """
    rankings = get_user_watch_time_rankings()

    for item in rankings:
        if item["user_id"] == user.id:
            return item["rank"]

    return None
