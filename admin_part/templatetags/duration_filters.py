from django import template
from admin_part.utils import format_duration

register = template.Library()

@register.filter
def duration_format(value):
    return format_duration(value)
