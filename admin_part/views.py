from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import *
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.text import slugify
from django.contrib.auth import logout
import json
from django.http import JsonResponse
from datetime import datetime, date, time
import uuid
import jwt
import requests
from auth_app.models import CustomUser
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import re
import time
import jwt  # PyJWT
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from .utils import get_video_duration,convert_to_hls 
# Create your views here.


def index(request):
    return render(request, 'index.html')



def admin_dashboard(request):
    # Bundle enrollment statistics
    bundle_stats = Bundle.objects.annotate(
        total_enrollments=Count('enrollments', filter=Q(enrollments__is_active=True)),
        paid_enrollments=Count('enrollments', filter=Q(enrollments__payment_status='completed')),
        free_enrollments=Count('enrollments', filter=Q(enrollments__payment_status='free')),
        completed_enrollments=Count('enrollments', filter=Q(enrollments__progress_percentage=100))
    ).order_by('-total_enrollments')
    
    # Overall statistics
    total_enrollments = Enrollment.objects.filter(is_active=True).count()
    total_paid_enrollments = Enrollment.objects.filter(payment_status='completed', is_active=True).count()
    total_free_enrollments = Enrollment.objects.filter(payment_status='free', is_active=True).count()
    total_completed_enrollments = Enrollment.objects.filter(progress_percentage=100, is_active=True).count()
    
    # Recent enrollments (last 7 days)
    recent_enrollments = Enrollment.objects.filter(
        enrolled_at__gte=timezone.now() - timedelta(days=7)
    ).select_related('user', 'bundle').order_by('-enrolled_at')[:10]
    
    context = {
        'bundle_stats': bundle_stats,
        'total_enrollments': total_enrollments,
        'total_paid_enrollments': total_paid_enrollments,
        'total_free_enrollments': total_free_enrollments,
        'total_completed_enrollments': total_completed_enrollments,
        'recent_enrollments': recent_enrollments,
    }
    
    return render(request, 'admin_dashboard.html', context)

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


def add_bundle(request):
    if request.method == "POST":
        name = request.POST.get('name')
        price = request.POST.get('price') or 0
        discount = request.POST.get('discount') or 0
        is_free = bool(request.POST.get('is_free'))
        short_description = request.POST.get('short_description')
        full_description = request.POST.get('full_description')
        is_published = bool(request.POST.get('is_published'))

        thumbnail = request.FILES.get('thumbnail')

        # ✅ Validation
        if not name:
            messages.error(request, "Name is required.")
            return redirect('add_category')

        # ✅ Create and save bundle
        category = Bundle(
            name=name,
            slug=slugify(name),
            price=price,
            discount=discount,
            is_free=is_free,
            short_description=short_description,
            full_description=full_description,
            thumbnail=thumbnail,
            is_published=is_published,
            created_at=timezone.now()
        )
        category.save()

        messages.success(request, f'Bundle "{category.name}" added successfully!')
        return redirect('bundles')

    return render(request, 'add_bundle.html')


def bundles(request):
    bundles = Bundle.objects.all().order_by('id')
    return render(request, 'bundles.html', {'bundles': bundles})

def delete_bundle(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    bundle.delete()
    messages.success(request, f'Bundle "{bundle.name}" has been deleted successfully.')
    return redirect('bundles')

def edit_bundle(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price = request.POST.get('price', 0)
        discount = request.POST.get('discount', 0)
        is_free = bool(request.POST.get('is_free'))
        short_description = request.POST.get('short_description', '').strip()
        full_description = request.POST.get('full_description', '').strip()
        is_published = bool(request.POST.get('is_published'))
        thumbnail = request.FILES.get('thumbnail')

        # Update fields
        bundle.name = name
        bundle.slug = slugify(name)
        bundle.price = price or 0
        bundle.discount = discount or 0
        bundle.is_free = is_free
        bundle.short_description = short_description
        bundle.full_description = full_description
        bundle.is_published = is_published

        # Replace thumbnail only if new file uploaded
        if thumbnail:
            bundle.thumbnail = thumbnail

        try:
            bundle.save()
            messages.success(request, "Bundle updated successfully!")
            return redirect('bundles')  # Adjust to your listing URL name
        except Exception as e:
            messages.error(request, f"Error updating bundle: {str(e)}")

    context = {
        'bundle': bundle
    }
    return render(request, 'edit_bundle.html', context)


def add_course(request):
    categories = Bundle.objects.all()
    print("hhhhhhhhhhhhhhh")
    if request.method == 'POST':
        try:
            print("jjjjjjjjjjjjjjjjjj")
            category_id = request.POST.get('category')
            print(category_id)
            category = Bundle.objects.get(id=category_id) if category_id else None
            print(category_id,category)
            title = request.POST.get('title')
            thumbnail = request.FILES.get('thumbnail')
            preview_video = request.FILES.get('preview_video')
            short_description = request.POST.get('short_description')
            full_description = request.POST.get('full_description')
            language = request.POST.get('language', 'English')
            level = request.POST.get('level', 'Beginner')
            course_includes = request.POST.get('course_includes', '')
            requirements = request.POST.get('requirements', '')
            learning_outcomes = request.POST.get('learning_outcomes', '')

            course = Course(
                bundle=category,
                title=title,
                thumbnail=thumbnail,
                preview_video=preview_video,
                short_description=short_description,
                full_description=full_description,
                language=language,
                level=level,
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
    bundles = Bundle.objects.all()
    bundle_id = request.GET.get('bundle_id')

    courses = Course.objects.select_related("bundle").all()
    if bundle_id:
        courses = courses.filter(bundle_id=bundle_id)

    return render(request, "view_course.html", {
        "bundles": bundles,
        "courses": courses,
    })

def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    categories = Bundle.objects.all()

    if request.method == "POST":
        try:
            course.title = request.POST.get('title')
            course.bundle_id = request.POST.get('category')
            course.short_description = request.POST.get('short_description')
            course.full_description = request.POST.get('full_description')
            course.language = request.POST.get('language')
            course.level = request.POST.get('level')
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

import os
def add_lecture(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        order = request.POST.get("order") or 0
        video = request.FILES.get("video")
        resource = request.FILES.get("resource")

        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect('course_detail', course_id=section.course.id)

        try:
            lecture = Lecture.objects.create(
                section=section,
                title=title,
                order=order,
                is_preview=is_preview,
                resource=resource,
                
            )

            # Save original video temporarily
            if video:
                video_path = os.path.join(settings.MEDIA_ROOT, "temp_videos", video.name)
                os.makedirs(os.path.dirname(video_path), exist_ok=True)
                with open(video_path, "wb+") as dest:
                    for chunk in video.chunks():
                        dest.write(chunk)

                # Convert to HLS
                hls_output_dir = os.path.join(settings.MEDIA_ROOT, "lectures", f"lecture_{lecture.id}")
                hls_rel_path = convert_to_hls(video_path, hls_output_dir)

                # Calculate duration
                duration = get_video_duration(video_path)
                lecture.duration = duration
                lecture.video = hls_rel_path
                lecture.save()

                # Cleanup temp file
                os.remove(video_path)

            messages.success(request, f"Lecture '{lecture.title}' added successfully!")

        except Exception as e:
            messages.error(request, f"Error adding lecture: {str(e)}")

        return redirect('course_detail', course_id=section.course.id)

    return render(request, 'add_lecture.html', {'section': section})


def edit_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        order = request.POST.get("order") or 0
        video = request.FILES.get("video")
        resource = request.FILES.get("resource")

        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect('course_detail', course_id=lecture.section.course.id)

        try:
            lecture.title = title
            lecture.is_preview = is_preview
            lecture.order = order

            # ✅ If new video uploaded, handle conversion and duration calculation
            if video:
                # Save original temporarily
                temp_path = os.path.join(settings.MEDIA_ROOT, "temp_videos", video.name)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)

                with open(temp_path, "wb+") as dest:
                    for chunk in video.chunks():
                        dest.write(chunk)

                # Convert to HLS (same as add_lecture)
                hls_output_dir = os.path.join(settings.MEDIA_ROOT, "lectures", f"lecture_{lecture.id}")
                hls_rel_path = convert_to_hls(temp_path, hls_output_dir)

                # Auto calculate video duration
                duration = get_video_duration(temp_path)

                # Update lecture fields
                lecture.video = hls_rel_path
                lecture.duration = duration

                # Cleanup temp video
                os.remove(temp_path)

            # ✅ Update resource if provided
            if resource:
                lecture.resource = resource

            lecture.save()
            messages.success(request, f"Lecture '{lecture.title}' updated successfully!")

        except Exception as e:
            messages.error(request, f"Error updating lecture: {str(e)}")

        return redirect('course_detail', course_id=lecture.section.course.id)
    
    # GET request → Render edit form
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
        meeting_number = request.POST.get('meeting_number')
        session_date = request.POST.get('session_date')
        session_time = request.POST.get('session_time')
        thumbnail = request.FILES.get('thumbnail')

        LiveSession.objects.create(
            title=title,
            agenda=agenda,
            meeting_number=meeting_number,
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


def _extract_meeting_number_from_join_url(join_url):
    """
    Extract Zoom meeting number from typical join_url patterns:
    e.g. https://us05web.zoom.us/j/86175242117?pwd=...  -> 86175242117
    Also supports /s/ style and other common variants.
    """
    if not join_url:
        return None
    patterns = [
        r'/j/(\d+)',   # /j/86175242117
        r'/s/(\d+)',   # /s/86175242117
        r'meeting\/(\d+)',  # possibly other formats
    ]
    for p in patterns:
        m = re.search(p, join_url)
        if m:
            return m.group(1)
    # fallback: find any 9-12 digit sequence
    m = re.search(r'(\d{9,12})', join_url)
    if m:
        return m.group(1)
    return None

def get_zoom_signature(request):
    """
    Endpoint that returns a JSON object: { signature: "...." }
    Expects GET params:
      - meetingNumber (optional) OR session_id (optional)
      - role (optional) 0 = participant / 1 = host (default 0)
    Example:
      /zoom/get_signature/?meetingNumber=86175242117&role=0
    """
    meeting_number = request.GET.get('meetingNumber')
    session_id = request.GET.get('session_id')
    role = int(request.GET.get('role') or 0)

    if session_id and not meeting_number:
        # if you prefer passing session id (DB) instead of meetingNumber:
        session = get_object_or_404(LiveSession, id=session_id)
        meeting_number = _extract_meeting_number_from_join_url(session.meeting_url)

    if not meeting_number:
        return HttpResponseBadRequest("Missing meetingNumber or invalid session_id/meeting_url.")

    try:
        sdk_key = settings.ZOOM_SDK_KEY
        sdk_secret = settings.ZOOM_SDK_SECRET
    except Exception:
        return HttpResponseBadRequest("Zoom SDK key/secret not configured on server.")

    # Build JWT payload according to Meeting SDK expectations
    iat = int(time.time())
    exp = iat + 120  # token valid for 2 minutes
    payload = {
        "sdkKey": sdk_key,
        "mn": str(meeting_number),
        "role": role,
        "iat": iat,
        "exp": exp,
        # appKey/appKey - sometimes samples include these fields; including them for compatibility:
        "appKey": sdk_key,
        "tokenExp": exp
    }

    # Create JWT using SDK secret (HS256)
    token = jwt.encode(payload, sdk_secret, algorithm="HS256")
    # PyJWT returns bytes in some versions; ensure string
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return JsonResponse({"signature": token})




def live_session_test(request):
    """Display all live sessions"""
    sessions = LiveSession.objects.all().order_by('-session_date', '-session_time')
    
    # Check if sessions are active based on current time
    current_datetime = datetime.now()
    for session in sessions:
        session_datetime = datetime.combine(session.session_date, session.session_time)
        # Consider session active if it's within 30 minutes of start time
        time_difference = (session_datetime - current_datetime).total_seconds()
        session.is_active = time_difference <= 1800  # 30 minutes before start
    
    return render(request, 'live_session_test.html', {'sessions': sessions})




def user_list(request):
    users = CustomUser.objects.filter(is_superuser=False).select_related('profile').order_by('-date_joined')
    return render(request, 'user_list.html', {'users': users})

def bundle_enrollment_details(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    
    # Get all enrollments for this bundle
    enrollments = Enrollment.objects.filter(
        bundle=bundle, 
        is_active=True
    ).select_related('user').order_by('-enrolled_at')
    
    # Enrollment statistics
    total_enrollments = enrollments.count()
    paid_enrollments = enrollments.filter(payment_status='completed').count()
    free_enrollments = enrollments.filter(payment_status='free').count()
    completed_enrollments = enrollments.filter(progress_percentage=100).count()
    
    # Progress distribution - use underscore instead of hyphen
    progress_distribution = {
        'progress_0_25': enrollments.filter(progress_percentage__range=(0, 25)).count(),
        'progress_26_50': enrollments.filter(progress_percentage__range=(26, 50)).count(),
        'progress_51_75': enrollments.filter(progress_percentage__range=(51, 75)).count(),
        'progress_76_99': enrollments.filter(progress_percentage__range=(76, 99)).count(),
        'progress_100': completed_enrollments
    }
    
    context = {
        'bundle': bundle,
        'enrollments': enrollments,
        'total_enrollments': total_enrollments,
        'paid_enrollments': paid_enrollments,
        'free_enrollments': free_enrollments,
        'completed_enrollments': completed_enrollments,
        'progress_distribution': progress_distribution,
    }
    
    return render(request, 'bundle_enrollment_details.html', context)

def total_enrollments(request):
    # Get all enrollments for admin view with optimized query
    all_enrollments = Enrollment.objects.all().select_related('bundle', 'user').prefetch_related('bundle__courses', 'bundle__enrollments')
    
    context = {
        'enrollments': all_enrollments
    }
    return render(request, 'total_enrollments.html', context)

def view_bundle_candidates(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    enrollments = Enrollment.objects.filter(bundle=bundle).select_related('user')
    
    context = {
        'bundle': bundle,
        'enrollments': enrollments
    }
    return render(request, 'bundle_candidates.html', context)


@ensure_csrf_cookie
def join_live_session(request, pk):
    session = get_object_or_404(LiveSession, pk=pk)
    
    # Check if session is active (optional)
    if not session.is_active():
        return render(request, "session_not_active.html", {"session": session})
    
    context = {
        "session": session,
        "ZOOM_SDK_KEY": settings.ZOOM_SDK_KEY
    }
    return render(request, "join_session.html", context)