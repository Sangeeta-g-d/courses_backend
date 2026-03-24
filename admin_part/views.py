from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import *
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.text import slugify
from django.contrib.auth import logout
import json
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
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
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from .utils import get_video_duration,convert_to_hls 
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
from django.views.decorators.http import require_GET
from .tasks import process_lecture_video
from django.conf import settings
from functools import wraps

# Create your views here.

# ============================================================================
# AUTHENTICATION & AUTHORIZATION DECORATORS
# ============================================================================

def admin_required(view_func):
    """
    Decorator to check if user is logged in and is a superuser.
    Redirects unauthenticated users to login page.
    Redirects non-superusers to access denied page.
    Also prevents caching to ensure secure content isn't cached.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user is not authenticated
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in first.")
            return redirect('admin_login')
        
        # Check if user is not a superuser
        if not request.user.is_superuser:
            response = render(request, 'admin_access_denied.html', status=403)
            # Add no-cache headers
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
        
        # User is authenticated and is a superuser
        response = view_func(request, *args, **kwargs)
        
        # Add no-cache headers to prevent browser caching of admin pages
        if hasattr(response, 'has_header'):  # Check if it's a proper HttpResponse
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response
    
    return wrapper


def index(request):
    return render(request, 'index.html')



@admin_required
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
    response = redirect('admin_login')
    # Prevent browser caching to ensure back button doesn't return to admin pages
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

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

    response = render(request, 'admin_login.html')
    # Add no-cache headers to prevent caching of login page
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@admin_required
def add_bundle(request):
    if request.method == "POST":
        name = request.POST.get('name')
        price = request.POST.get('price') or 0
        discount = request.POST.get('discount') or 0
        is_free = bool(request.POST.get('is_free'))
        short_description = request.POST.get('short_description')
        full_description = request.POST.get('full_description')
        is_published = bool(request.POST.get('is_published'))
        bundle_pdf_price = request.POST.get('bundle_pdf_price') or None

        thumbnail = request.FILES.get('thumbnail')
        preview_video = request.FILES.get('preview_video')
        bundle_pdf = request.FILES.get('bundle_pdf')
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
            preview_video=preview_video,
            bundle_pdf=bundle_pdf,
            bundle_pdf_price=bundle_pdf_price,
            is_published=is_published,
            created_at=timezone.now()
        )
        category.save()
        messages.success(request, f'Course "{category.name}" added successfully!')
        return redirect('bundles')
    return render(request, 'add_bundle.html')


@admin_required
def bundles(request):
    bundles = Bundle.objects.all().order_by('id')
    return render(request, 'bundles.html', {'bundles': bundles})

@admin_required
def delete_bundle(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    bundle.delete()
    messages.success(request, f'Course "{bundle.name}" has been deleted successfully.')
    return redirect('bundles')

@admin_required
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
        bundle_pdf_price = request.POST.get('bundle_pdf_price') or None
        
        thumbnail = request.FILES.get('thumbnail')
        preview_video = request.FILES.get('preview_video')
        bundle_pdf = request.FILES.get('bundle_pdf')
        
        # Update fields
        bundle.name = name
        bundle.slug = slugify(name)
        bundle.price = price or 0
        bundle.discount = discount or 0
        bundle.is_free = is_free
        bundle.short_description = short_description
        bundle.full_description = full_description
        bundle.is_published = is_published
        bundle.bundle_pdf_price = bundle_pdf_price

        # Replace thumbnail only if new file uploaded
        if thumbnail:
            bundle.thumbnail = thumbnail
        
        # Replace preview video only if new file uploaded
        if preview_video:
            bundle.preview_video = preview_video
        
        # Replace PDF only if new file uploaded
        if bundle_pdf:
            bundle.bundle_pdf = bundle_pdf
        
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


@admin_required
def add_course(request):
    categories = Bundle.objects.all()
    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            category = Bundle.objects.get(id=category_id) if category_id else None
            title = request.POST.get('title')
            thumbnail = request.FILES.get('thumbnail')
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

@admin_required
def view_courses(request):
    bundles = Bundle.objects.all()
    bundle_id = request.GET.get('bundle_id')

    selected_bundle = None
    courses = Course.objects.select_related("bundle").all()

    if bundle_id:
        selected_bundle = Bundle.objects.filter(id=bundle_id).first()
        courses = courses.filter(bundle_id=bundle_id)

    return render(request, "view_course.html", {
        "bundles": bundles,
        "courses": courses,
        "selected_bundle": selected_bundle,
    })


@require_POST
@admin_required
def toggle_course_publish(request, course_id):
    try:
        # Parse JSON data
        data = json.loads(request.body)
        is_published = data.get("is_published", False)
        
        # Get the course
        course = Course.objects.get(id=course_id)
        
        # Update the field
        course.is_published = is_published
        course.save()
        
        # Return success response
        return JsonResponse({
            "success": True,
            "is_published": course.is_published,
            "message": f"Course '{course.title}' is now {'published' if is_published else 'unpublished'}"
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False, 
            "error": "Invalid JSON data"
        }, status=400)
        
    except Course.DoesNotExist:
        return JsonResponse({
            "success": False, 
            "error": "Course not found"
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "error": str(e)
        }, status=400)
    
@admin_required
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

            course.save()
            messages.success(request, "Course updated successfully!")
            return redirect('/view_courses/')  # your course list view
        except Exception as e:
            messages.error(request, f"Error updating course: {str(e)}")
    return render(request, 'edit_course.html', {'course': course, 'categories': categories})


@admin_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, "Course deleted successfully!")
    return redirect('view_courses')


@admin_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'course_detail.html', {'course': course})

@admin_required
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

        try:
            section = CourseSection.objects.create(
                course=course,
                title=title,
                order=order,
               
            )
            messages.success(request, f"Section '{section.title}' added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding section: {str(e)}")

    return redirect('course_detail', course_id=course_id)

@admin_required
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

@admin_required
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

@admin_required
def add_lecture(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        order = request.POST.get("order") or 0

        # 🔹 LOCAL upload
        video_file = request.FILES.get("video")

        # 🔹 PRODUCTION upload (direct S3)
        s3_key = request.POST.get("s3_key")

        resource = request.FILES.get("resource")
        thumbnail = request.FILES.get("thumbnail")

        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect("course_detail", course_id=section.course.id)

        if not video_file and not s3_key:
            messages.error(request, "Video is required.")
            return redirect("course_detail", course_id=section.course.id)

        try:
            lecture = Lecture.objects.create(
                section=section,
                title=title,
                order=order,
                is_preview=is_preview,

                # ✅ Local OR S3 (only one will be filled)
                original_video_file=video_file if video_file else None,
                original_video_key=s3_key if s3_key else None,

                resource=resource,
                thumbnail=thumbnail,
                processing_status="pending",
            )

            # ✅ Background processing
            process_lecture_video.delay(lecture.id)

            messages.success(
                request,
                f"Lecture '{lecture.title}' uploaded. Video processing started."
            )

        except Exception as e:
            messages.error(request, f"Error adding lecture: {str(e)}")

        return redirect("course_detail", course_id=section.course.id)

    return render(request, "add_lecture.html", {"section": section})

@admin_required
def edit_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        is_preview = request.POST.get("is_preview") == "on"
        order_raw = request.POST.get("order", "").strip()

        # 🔹 Local upload
        video_file = request.FILES.get("video")
        # 🔹 Direct S3 upload
        s3_key = request.POST.get("s3_key")

        resource = request.FILES.get("resource")
        remove_thumbnail = request.POST.get("remove_thumbnail")  # checkbox
        new_thumbnail = request.FILES.get('thumbnail')

        # Validate title
        if not title:
            messages.error(request, "Lecture title is required.")
            return redirect('course_detail', course_id=lecture.section.course.id)

        # Validate order
        if order_raw != "":
            try:
                order = int(order_raw)
            except ValueError:
                messages.error(request, "Order must be a number.")
                return redirect('course_detail', course_id=lecture.section.course.id)
        else:
            order = lecture.order or 0

        try:
            lecture.title = title
            lecture.is_preview = is_preview
            lecture.order = order

            # ---------- Handle new video upload ----------
            if video_file or s3_key:
                # Delete old videos (optional)
                if lecture.original_video_file:
                    try:
                        lecture.original_video_file.delete(save=False)
                    except Exception:
                        pass
                if lecture.original_video_key:
                    # S3 key does not need delete, optional if you want to remove old key
                    pass
                if lecture.processed_video:
                    try:
                        lecture.processed_video.delete(save=False)
                    except Exception:
                        pass

                # Save new video (local or S3)
                lecture.original_video_file = video_file if video_file else None
                lecture.original_video_key = s3_key if s3_key else None
                lecture.processing_status = "pending"
                lecture.save(update_fields=["original_video_file", "original_video_key", "processing_status"])

                # Send to Celery for background processing
                process_lecture_video.delay(lecture.id)

            # ---------- Handle resource upload ----------
            if resource:
                if lecture.resource:
                    try:
                        lecture.resource.delete(save=False)
                    except Exception:
                        pass
                lecture.resource = resource

            # ---------- Handle thumbnail removal ----------
            if remove_thumbnail and lecture.thumbnail:
                try:
                    lecture.thumbnail.delete(save=False)
                except Exception:
                    pass
                lecture.thumbnail = None

            # ---------- Handle new thumbnail upload ----------
            if new_thumbnail:
                if lecture.thumbnail:
                    try:
                        lecture.thumbnail.delete(save=False)
                    except Exception:
                        pass
                lecture.thumbnail = new_thumbnail

            # Save other changes
            lecture.save()
            messages.success(request, f"Lecture '{lecture.title}' updated successfully!")

        except Exception as e:
            messages.error(request, f"Error updating lecture: {str(e)}")

        return redirect('course_detail', course_id=lecture.section.course.id)

    # GET → render edit page
    return render(request, 'edit_lecture.html', {'lecture': lecture})

@admin_required
def delete_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    course_id = lecture.section.course.id
    try:
        lecture.delete()
        messages.success(request, f"Lecture '{lecture.title}' deleted successfully!")
    except Exception as e:
        messages.error(request, f"Error deleting lecture: {str(e)}")
    return redirect('course_detail', course_id=course_id)



@admin_required
def user_list(request):
    users = CustomUser.objects.filter(is_superuser=False).select_related('profile').order_by('-date_joined')
    return render(request, 'user_list.html', {'users': users})


def user_detail(request, user_id):
    """Return HTML snippet with the user's information for the modal."""
    user = get_object_or_404(CustomUser, id=user_id)
    return render(request, 'user_detail_partial.html', {'user': user})

def edit_user(request, user_id):
    """Render a simple edit form and process updates."""
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        # only allow a few editable fields for now
        user.full_name = request.POST.get('full_name', user.full_name)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.is_active = bool(request.POST.get('is_active'))
        # update profile fields if present
        profile = getattr(user, 'profile', None)
        if profile:
            profile.city = request.POST.get('city', profile.city)
            profile.highest_qualification = request.POST.get('highest_qualification', profile.highest_qualification)
            profile.save()
        user.save()
        messages.success(request, 'User details updated successfully.')
        return redirect('user_list')
    return render(request, 'edit_user.html', {'user': user})


@require_POST
def toggle_user_status(request, user_id):
    """Enable/disable a user account via AJAX."""
    user = get_object_or_404(CustomUser, id=user_id)
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({'success': True, 'is_active': user.is_active})

@admin_required
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

@admin_required
def total_enrollments(request):
    # Get bundles with enrollment count (grouped by bundle)
    from django.db.models import Count
    
    bundles_with_enrollments = Bundle.objects.annotate(
        enrollment_count=Count('enrollments')
    ).prefetch_related('courses', 'enrollments').filter(enrollment_count__gt=0).order_by('-enrollment_count')
    
    context = {
        'bundles': bundles_with_enrollments
    }
    return render(request, 'total_enrollments.html', context)

@admin_required
def view_bundle_candidates(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    enrollments = Enrollment.objects.filter(bundle=bundle).select_related('user')
    
    context = {
        'bundle': bundle,
        'enrollments': enrollments
    }
    return render(request, 'bundle_candidates.html', context)



@admin_required
def admin_live_sessions(request):
    sessions = LiveSession.objects.all().order_by('-session_date', '-session_time')
    return render(request, 'live_sessions_list.html', {'sessions': sessions})


# Admin: Add session
@admin_required
def add_live_session(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        agenda = request.POST.get('agenda')
        meeting_number = request.POST.get('meeting_number')
        passcode = request.POST.get('Passcode')
        session_date = request.POST.get('session_date')
        session_time = request.POST.get('session_time')
        session_type = request.POST.get('session_type', 'webinar')
        thumbnail = request.FILES.get('thumbnail')

        session = LiveSession.objects.create(
            title=title,
            agenda=agenda,
            meeting_number=meeting_number,
            Passcode=passcode,
            session_date=session_date,
            session_time=session_time,
            session_type=session_type,
            thumbnail=thumbnail
        )

        # Create a corresponding zoom post for this session
        Post.objects.create(
            caption=agenda or "",
            image1=thumbnail,
            post_type="zoom_post",
            session=session,
            is_active=True,
        )
        messages.success(request, "Live session added successfully.")
        return redirect('admin_live_sessions')

    return render(request, 'add_live_session.html')


@admin_required
def edit_live_session(request, session_id):
    session = get_object_or_404(LiveSession, id=session_id)

    if request.method == 'POST':
        session.title = request.POST.get('title')
        session.agenda = request.POST.get('agenda')
        session.meeting_number = request.POST.get('meeting_id')
        session.Passcode = request.POST.get('passcode')
        session.session_date = request.POST.get('session_date')
        session.session_time = request.POST.get('session_time')
        session.session_type = request.POST.get('session_type', 'webinar')

        if request.FILES.get('thumbnail'):
            session.thumbnail = request.FILES.get('thumbnail')

        session.save()
        messages.success(request, "Live session updated successfully.")
        return redirect('admin_live_sessions')

    return render(request, 'edit_live_session.html', {'session': session})


# Admin: Delete session
@admin_required
def delete_live_session(request, session_id):
    session = get_object_or_404(LiveSession, id=session_id)
    session.delete()
    messages.success(request, "Live session deleted successfully.")
    return redirect('admin_live_sessions')





@admin_required
def join_live_session(request, session_id):
    from django.conf import settings
    session = get_object_or_404(LiveSession, id=session_id)
    context = {
        'session': session,
        'zoom_sdk_key': settings.ZOOM_SDK_KEY,
    }
    return render(request, 'join_zoom_meeting.html', context)


@require_GET
@csrf_exempt
def zoom_sdk_signature(request):
    """Generate JWT signature for Zoom SDK"""
    meeting_number = request.GET.get("meetingNumber")
    role = request.GET.get("role", "0")

    if not meeting_number:
        return HttpResponseBadRequest("meetingNumber parameter is required")

    try:
        role = int(role)
    except ValueError:
        return HttpResponseBadRequest("role must be 0 or 1")

    sdk_key = settings.ZOOM_SDK_KEY
    sdk_secret = settings.ZOOM_SDK_SECRET

    if not sdk_key or not sdk_secret:
        return JsonResponse({"error": "Zoom SDK credentials missing"}, status=500)

    iat = int(time.time())
    exp = iat + 60 * 60 * 2  # 2 hours

    payload = {
        "appKey": sdk_key,
        "sdkKey": sdk_key,
        "mn": meeting_number,
        "role": role,
        "iat": iat,
        "exp": exp,
        "tokenExp": exp
    }

    try:
        signature = jwt.encode(payload, sdk_secret, algorithm="HS256")
        if isinstance(signature, bytes):
            signature = signature.decode("utf-8")
        return JsonResponse({"signature": signature, "meetingNumber": meeting_number})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



@admin_required
def contact_list(request):
    contacts = ContactMessage.objects.all().order_by('-created_at')
    return render(request, 'contact_list.html', {'contacts': contacts})


@admin_required
def banner_list(request):
    banners = Banner.objects.all().order_by('-created_at')
    return render(request, 'banner_list.html', {'banners': banners})


@admin_required
def add_banner(request):
    if request.method == "POST":
        image = request.FILES.get("image")
        if not image:
            messages.error(request, "Please upload an image.")
            return redirect("add_banner")

        Banner.objects.create(image=image)
        messages.success(request, "Banner added successfully.")
        return redirect("banner_list")

    return render(request, "add_banner.html")


@admin_required
def delete_banner(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    if request.method == "POST":
        banner.delete()
        messages.success(request, "Banner deleted successfully.")
    else:
        messages.error(request, "Invalid request.")
    return redirect("banner_list")

@admin_required
def add_post(request):
    if request.method == "POST":
        caption = request.POST.get("caption", "").strip()
        is_active = request.POST.get("is_active") == "on"

        image1 = request.FILES.get("image1")
        image2 = request.FILES.get("image2")
        image3 = request.FILES.get("image3")

        # 🔒 Validation: at least one image OR caption
        if not caption and not any([image1, image2, image3]):
            messages.error(
                request,
                "Please add at least one image or a caption."
            )
            return redirect("add_post")

        Post.objects.create(
            caption=caption,
            image1=image1,
            image2=image2,
            image3=image3,
            is_active=is_active,
            post_type="post"
        )

        messages.success(request, "Post added successfully!")
        return redirect("add_post")

    return render(request, "add_post.html")


@admin_required
def post_list(request):
    posts = Post.objects.order_by('-created_at')

    today = timezone.now()
    first_day = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    context = {
        'posts': posts,
        'stats': {
            'count': posts.count(),
            'active_count': posts.filter(is_active=True).count(),
            'this_month_count': posts.filter(created_at__gte=first_day).count(),
        }
    }
    return render(request, 'post_list.html', context)


@admin_required
def delete_post(request, id):
    post = get_object_or_404(Post, id=id)

    if request.method == "POST":
        post.delete()
        messages.success(request, "Post deleted successfully.")
    else:
        messages.error(request, "Invalid request.")

    return redirect(request.META.get('HTTP_REFERER', 'post_list'))

@admin_required
def edit_post(request, id):
    post = get_object_or_404(Post, id=id)

    if request.method == "POST":
        post.caption = request.POST.get("caption", "").strip()
        post.is_active = request.POST.get("is_active") == "on"

        # Update images only if new file is uploaded
        if request.FILES.get("image1"):
            post.image1 = request.FILES["image1"]

        if request.FILES.get("image2"):
            post.image2 = request.FILES["image2"]

        if request.FILES.get("image3"):
            post.image3 = request.FILES["image3"]

        post.save()
        messages.success(request, "Post updated successfully!")
        return redirect("post_list")

    return render(request, "edit_post.html", {"post": post})


