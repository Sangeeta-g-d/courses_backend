from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import *
from django.utils.text import slugify
from django.contrib.auth import logout
import json
from django.http import JsonResponse
# Create your views here.


def index(request):
    return render(request, 'index.html')


def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

def admin_logout(request):
    logout(request)
    return redirect('admin_login')

def admin_login(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')  # ✅ checkbox value

        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_superuser:
            login(request, user)

            # ✅ Session expiry logic
            if not remember_me:
                request.session.set_expiry(0)  # Session ends when browser closes
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days

            messages.success(request, f"Welcome back, {user.email}!")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid credentials or not an admin user.")

    return render(request, 'admin_login.html')

def categories(request):
    categories = Category.objects.all().order_by('id')
    return render(request, 'categories.html', {'categories': categories})

def save_category(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        category_id = request.POST.get("category_id")

        if not name:
            messages.error(request, "Category name cannot be empty.")
            return redirect('categories')

        if category_id:  # Update existing
            category = get_object_or_404(Category, id=category_id)
            category.name = name
            category.slug = slugify(name)
            category.save()
            messages.success(request, f"Category '{name}' updated successfully!")
        else:  # Add new
            if Category.objects.filter(name__iexact=name).exists():
                messages.warning(request, "Category with this name already exists.")
            else:
                Category.objects.create(name=name, slug=slugify(name))
                messages.success(request, f"Category '{name}' added successfully!")

        return redirect('categories')
    else:
        messages.error(request, "Invalid request.")
        return redirect('categories')


def delete_category(request, pk):
    category = get_object_or_404(Category, id=pk)
    category.delete()
    messages.success(request, f"Category '{category.name}' deleted successfully!")
    return redirect('categories')


def course_form(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        instructor_id = request.POST.get('instructor')
        category_id = request.POST.get('category')
        title = request.POST.get('title')
        short_description = request.POST.get('short_description')
        full_description = request.POST.get('full_description')
        language = request.POST.get('language', 'English')
        level = request.POST.get('level', 'Beginner')
        price = request.POST.get('price', 0.00)
        discount = request.POST.get('discount', 0)
        is_free = 'is_free' in request.POST
        is_published = 'is_published' in request.POST
        course_includes = request.POST.get('course_includes', '')
        requirements = request.POST.get('requirements', '')
        learning_outcomes = request.POST.get('learning_outcomes', '')

        thumbnail = request.FILES.get('thumbnail')
        preview_video = request.FILES.get('preview_video')

        # Basic Validation
        if not (instructor_id and category_id and title and short_description and full_description):
            messages.error(request, "Please fill all required fields.")
            return redirect('course_form')

        # Create Course Object
        try:
           
            category = Category.objects.get(id=category_id)

            course = Course.objects.create(
                category=category,
                title=title,
                slug=slugify(title),
                short_description=short_description,
                full_description=full_description,
                language=language,
                level=level,
                price=price if not is_free else 0,
                discount=discount,
                is_free=is_free,
                course_includes=course_includes,
                requirements=requirements,
                learning_outcomes=learning_outcomes,
                is_published=is_published,
                thumbnail=thumbnail,
                preview_video=preview_video
            )

            messages.success(request, f"Course '{course.title}' added successfully!")
            return redirect('courses_list')  # change to your actual course list URL name
        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
        except Exception as e:
            messages.error(request, f"Something went wrong: {str(e)}")

        return redirect('course_form')

    return render(request, 'course_form.html', {
        'categories': categories,
    })


def add_course(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            category = Category.objects.get(id=category_id) if category_id else None

            title = request.POST.get('title')
            thumbnail = request.FILES.get('thumbnail')
            preview_video = request.FILES.get('preview_video')
            short_description = request.POST.get('short_description')
            full_description = request.POST.get('full_description')
            language = request.POST.get('language', 'English')
            level = request.POST.get('level', 'Beginner')
            price = float(request.POST.get('price', 0))
            discount = int(request.POST.get('discount', 0))
            is_free = request.POST.get('is_free') == 'on'
            course_includes = request.POST.get('course_includes', '')
            requirements = request.POST.get('requirements', '')
            learning_outcomes = request.POST.get('learning_outcomes', '')

            course = Course(
                category=category,
                title=title,
                thumbnail=thumbnail,
                preview_video=preview_video,
                short_description=short_description,
                full_description=full_description,
                language=language,
                level=level,
                price=price,
                discount=discount,
                is_free=is_free,
                course_includes=course_includes,
                requirements=requirements,
                learning_outcomes=learning_outcomes
            )
            course.save()
            messages.success(request, "Course added successfully!")
            return redirect('add_course')
        except Exception as e:
            messages.error(request, f"Error adding course: {str(e)}")
            return redirect('add_course')

    return render(request, 'add_course.html', {'categories': categories})

def view_courses(request):
    courses = Course.objects.all().order_by('-created_at')
    return render(request, 'view_course.html', {'courses': courses})

def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    categories = Category.objects.all()

    if request.method == "POST":
        try:
            course.title = request.POST.get('title')
            course.category_id = request.POST.get('category')
            course.short_description = request.POST.get('short_description')
            course.full_description = request.POST.get('full_description')
            course.language = request.POST.get('language')
            course.level = request.POST.get('level')
            course.is_free = True if request.POST.get('is_free') == 'on' else False
            course.price = request.POST.get('price') if not course.is_free else 0
            course.discount = request.POST.get('discount') if not course.is_free else 0
            course.course_includes = request.POST.get('course_includes')
            course.requirements = request.POST.get('requirements')
            course.learning_outcomes = request.POST.get('learning_outcomes')

            # Handle file uploads
            if 'thumbnail' in request.FILES:
                course.thumbnail = request.FILES['thumbnail']
            if 'preview_video' in request.FILES:
                course.preview_video = request.FILES['preview_video']

            course.save()
            messages.success(request, "Course updated successfully!")
            return redirect('/view_courses/')  # your course list view
        except Exception as e:
            messages.error(request, f"Error updating course: {str(e)}")

    return render(request, 'edit_course.html', {'course': course, 'categories': categories})


def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, "Course deleted successfully!")
    return redirect('view_courses')


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'course_detail.html', {'course': course})

def add_section(request, course_id):
    if request.method == "POST":
        course = get_object_or_404(Course, id=course_id)
        title = request.POST.get('title', '').strip()
        order = request.POST.get('order', '').strip()

        # Backend Validation
        if not title:
            messages.error(request, "Section title is required.")
            return redirect('course_detail', course_id=course.id)

        if not order:
            order = course.course_sections.count() + 1
        else:
            try:
                order = int(order)
            except ValueError:
                messages.error(request, "Order must be a number.")
                return redirect('course_detail', course_id=course.id)

        # Create the section
        try:
            section = CourseSection.objects.create(
                course=course,
                title=title,
                order=order
            )
            messages.success(request, f"Section '{section.title}' added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding section: {str(e)}")

    return redirect('course_detail', course_id=course_id)


def edit_section(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id)
    course_id = section.course.id

    if request.method == "POST":
        title = request.POST.get('title', '').strip()
        order = request.POST.get('order', '').strip()

        # Validation
        if not title:
            messages.error(request, "Section title is required.")
            return redirect('course_detail', course_id=course_id)

        if order:
            try:
                order = int(order)
                section.order = order
            except ValueError:
                messages.error(request, "Order must be a number.")
                return redirect('course_detail', course_id=course_id)

        section.title = title

        try:
            section.save()
            messages.success(request, f"Section '{section.title}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating section: {str(e)}")

    return redirect('course_detail', course_id=course_id)

def delete_section(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id)
    course_id = section.course.id  # to redirect back

    try:
        section.delete()
        messages.success(request, f"Section '{section.title}' deleted successfully!")
    except Exception as e:
        messages.error(request, f"Error deleting section: {str(e)}")

    return redirect('course_detail', course_id=course_id)

def add_lecture(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id)
    
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        duration = request.POST.get("duration", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        video = request.FILES.get("video")
        resource = request.FILES.get("resource")
        order = request.POST.get("order") or 0

        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect('course_detail', course_id=section.course.id)

        try:
            lecture = Lecture.objects.create(
                section=section,
                title=title,
                duration=duration,
                is_preview=is_preview,
                video=video,
                resource=resource,
                order=order
            )
            messages.success(request, f"Lecture '{lecture.title}' added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding lecture: {str(e)}")

        return redirect('course_detail', course_id=section.course.id)
    
    # GET request can optionally render a modal or separate template if needed
    return render(request, 'add_lecture.html', {'section': section})


def edit_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        duration = request.POST.get("duration", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        video = request.FILES.get("video")
        resource = request.FILES.get("resource")
        order = request.POST.get("order") or 0

        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect('course_detail', course_id=lecture.section.course.id)

        try:
            lecture.title = title
            lecture.duration = duration
            lecture.is_preview = is_preview
            lecture.order = order
            if video:
                lecture.video = video
            if resource:
                lecture.resource = resource
            lecture.save()
            messages.success(request, f"Lecture '{lecture.title}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating lecture: {str(e)}")

        return redirect('course_detail', course_id=lecture.section.course.id)
    
    # GET request to render form (optional modal)
    return render(request, 'edit_lecture.html', {'lecture': lecture})

def delete_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    course_id = lecture.section.course.id
    try:
        lecture.delete()
        messages.success(request, f"Lecture '{lecture.title}' deleted successfully!")
    except Exception as e:
        messages.error(request, f"Error deleting lecture: {str(e)}")
    return redirect('course_detail', course_id=course_id)




# add session
def admin_live_sessions(request):
    sessions = LiveSession.objects.all().order_by('-session_date', '-session_time')
    return render(request, 'live_sessions_list.html', {'sessions': sessions})


# Admin: Add session
def add_live_session(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        agenda = request.POST.get('agenda')
        meeting_url = request.POST.get('google_meet_url')
        session_date = request.POST.get('session_date')
        session_time = request.POST.get('session_time')
        thumbnail = request.FILES.get('thumbnail')

        LiveSession.objects.create(
            title=title,
            agenda=agenda,
            meeting_url=meeting_url,
            session_date=session_date,
            session_time=session_time,
            thumbnail=thumbnail
        )
        messages.success(request, "Live session added successfully.")
        return redirect('admin_live_sessions')

    return render(request, 'add_live_session.html')


# Admin: Edit session
def edit_live_session(request, session_id):
    session = get_object_or_404(LiveSession, id=session_id)
    if request.method == 'POST':
        session.title = request.POST.get('title')
        session.agenda = request.POST.get('agenda')
        session.zoom_meeting_url = request.POST.get('zoom_meeting_url')
        session.session_date = request.POST.get('session_date')
        session.session_time = request.POST.get('session_time')

        if request.FILES.get('thumbnail'):
            session.thumbnail = request.FILES.get('thumbnail')

        session.save()
        messages.success(request, "Live session updated successfully.")
        return redirect('admin_live_sessions')

    return render(request, 'edit_live_session.html', {'session': session})


# Admin: Delete session
def delete_live_session(request, session_id):
    session = get_object_or_404(LiveSession, id=session_id)
    session.delete()
    messages.success(request, "Live session deleted successfully.")
    return redirect('admin_live_sessions')


def live_session_test(request):
    sessions = LiveSession.objects.all().order_by('-session_date', '-session_time')
    return render(request, 'live_session_test.html', {'sessions': sessions})