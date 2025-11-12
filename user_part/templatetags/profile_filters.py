from django import template

register = template.Library()

@register.filter
def format_learning_time(minutes):
    """Convert minutes to hours if more than 60 minutes"""
    if minutes >= 60:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"
    return f"{minutes}m"

@register.filter
def get_user_display(user, current_user):
    """Get user display name with 'You' for current user"""
    if user == current_user:
        return "You"
    return user.full_name or user.email