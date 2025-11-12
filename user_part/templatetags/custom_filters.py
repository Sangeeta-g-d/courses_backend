from django import template

register = template.Library()

@register.filter
def get_completed_count(lectures_count, lectures):
    """Count completed lectures in a section"""
    return sum(1 for lecture in lectures if lecture['completed'])