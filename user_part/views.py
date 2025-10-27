from django.shortcuts import render, get_object_or_404
from admin_part.models import Course, CourseSection, Lecture
# Create your views here.


def home(request):
    return render(request, 'home.html')

def user_course_detail(request):
    # If no course_id provided, use course with ID 2 as default
    
    course_id = 2
    
    # Get the course with all related sections and lectures
    course = get_object_or_404(
        Course.objects.prefetch_related(
            'course_sections__lectures'
        ),
        id=course_id
    )
    
    context = {
        'course': course,
    }
    
    return render(request, 'course.html', context)