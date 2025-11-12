# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from admin_part.models import UserProgress, UserStats

@receiver(post_save, sender=UserProgress)
def update_user_stats_on_progress(sender, instance, **kwargs):
    """Update user stats when progress is saved"""
    try:
        user_stats, created = UserStats.objects.get_or_create(user=instance.user)
        user_stats.update_stats()
    except Exception as e:
        print(f"Error updating user stats: {e}")