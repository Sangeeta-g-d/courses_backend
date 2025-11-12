from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def duration_format(seconds):
    """Template filter to format duration in seconds to human readable format"""
    # Convert SafeString to float if needed
    try:
        if hasattr(seconds, '__float__'):
            seconds_float = float(seconds)
        else:
            seconds_float = float(str(seconds))
    except (ValueError, TypeError):
        return "0:00"
    
    # Now use the format_duration function from utils
    from admin_part.utils import format_duration
    return format_duration(seconds_float)