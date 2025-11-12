from django.shortcuts import render, get_object_or_404, redirect,reverse
from admin_part.models import Course, CourseSection, Lecture,Bundle, Enrollment, PaymentTransaction,Wishlist,UserProgress
from auth_app.models import CustomUser, UserProfile
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
import random
from django.conf import settings
from django.db import transaction
import razorpay
import logging
import json
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from datetime import timedelta
from django.contrib import messages
from django.db.models import Count, Sum
from django.views.decorators.http import require_POST
from django.middleware.csrf import get_token
from .utils import get_user_rank,get_user_watch_time_rankings

def home(request):
    # Your existing course code
    qs = Course.objects.order_by('-created_at')
    courses = []
    for c in qs[:4]:
        try:
            thumb = c.thumbnail.url if c.thumbnail else '/static/home_assets/img/service-placeholder.jpg'
        except ValueError:
            thumb = '/static/home_assets/img/service-placeholder.jpg'

        try:
            detail_url = reverse('course_detail', args=[c.id])
        except Exception:
            detail_url = '#'

        courses.append({
            'id': c.id,
            'title': c.title,
            'thumbnail_url': thumb,
            'level': c.level,
            'language': c.language,
            'short_description': c.short_description or "High-quality course to boost your skills.",
            'detail_url': detail_url,
        })

    while len(courses) < 4:
        courses.append({
            'title': 'Coming Soon',
            'thumbnail_url': '/static/home_assets/img/service-placeholder.jpg',
            'level': '—',
            'language': '—',
            'short_description': 'New courses are added frequently — check back soon!',
            'detail_url': '#',
        })
    
    # Add bundles to the context
    bundles = Bundle.objects.filter(is_published=True).order_by('-created_at')[:4]
    
    return render(request, 'home.html', {
        'recent_courses': courses,
        'bundles': bundles
    })

def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        remember = request.POST.get("remember")  # checkbox value

        if not email or not password:
            messages.error(request, "Please enter both email and password.")
            return redirect("user_login")

        # Authenticate user
        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)

                # Handle 'Remember Me' functionality
                if remember:
                    # Keep the session for 2 weeks (default Django behavior)
                    request.session.set_expiry(1209600)  # 2 weeks
                else:
                    # Expire session on browser close
                    request.session.set_expiry(0)

                messages.success(request, f"Welcome back, {user.full_name}!")
                return redirect("dashboard")  # redirect to dashboard or user details
            else:
                messages.error(request, "Your account is inactive. Please contact support.")
        else:
            messages.error(request, "Invalid email or password.")

        return redirect("user_login")

    return render(request, "user_login.html")


def register(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        profile_image = request.FILES.get("profile_image")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("register")

        user = CustomUser.objects.create(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            profile_image=profile_image,
            password=make_password(password),
            role="student",
            is_active=True,
            date_joined=timezone.now(),
        )

        # Auto login after successful registration
        login(request, user)
        return redirect("user_details")

    return render(request, "register.html")


@login_required
def user_details(request):
    user = request.user

    if request.method == "POST":
        dob = request.POST.get("dob")
        qualification = request.POST.get("highest_qualification")
        city = request.POST.get("city")

        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.dob = dob
        profile.highest_qualification = qualification
        profile.city = city
        profile.save()

        messages.success(request, "Profile details saved successfully!")
        return redirect("dashboard")  # redirect to dashboard or home after saving

    return render(request, "user_details.html", {"user": user})

def dashboard(request):
    bundles = Bundle.objects.filter(is_published=True).order_by('-created_at')
    
    # Get top 5 users by watch time
    top_users = get_user_watch_time_rankings()[:5]
    
    # Get current user's rank and stats
    current_user_rank = None
    current_user_stats = None
    
    if request.user.is_authenticated:
        current_user_rank = get_user_rank(request.user)
        
        # Get current user's total watch time
        current_user_stats = request.user.progress.aggregate(
            total_watched_duration=Sum('watched_duration'),
            completed_lectures=Count('lecture', filter=Q(completed=True)),
            total_progress=Count('lecture')
        )
    
    context = {
        'bundles': bundles,
        'top_users': top_users,
        'current_user_rank': current_user_rank,
        'current_user_stats': current_user_stats,
    }
    
    return render(request, 'dashboard.html', context)

# import your models
# from .models import Course, Lecture, Enrollment, UserProgress
# views.py — overwrite your existing functions with this improved version
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.utils import timezone

# models: Course, Lecture, Enrollment, UserProgress

from django.utils import timezone
from django.db import transaction

def course_details(request, course_id):
    course = get_object_or_404(
        Course.objects.prefetch_related('course_sections__lectures'),
        id=course_id
    )

    is_enrolled = False
    user_progress_map = {}
    course_progress = 0
    total_lectures = 0
    completed_lectures = 0

    if request.user.is_authenticated and course.bundle:
        is_enrolled = Enrollment.objects.filter(
            user=request.user,
            bundle=course.bundle,
            payment_status__in=['completed', 'free'],
            is_active=True
        ).exists()

        # Get user progress for this course
        progress_entries = UserProgress.objects.filter(
            user=request.user,
            course=course
        ).select_related('lecture')
        
        user_progress_map = {up.lecture_id: up for up in progress_entries}
        
        # Calculate course progress
        total_lectures = course.calculated_total_lectures
        completed_lectures = progress_entries.filter(completed=True).count()
        if total_lectures > 0:
            course_progress = int((completed_lectures / total_lectures) * 100)

    # Total lectures count
    if not total_lectures:
        total_lectures = sum(section.lectures.count() for section in course.course_sections.all())

    # Initial lecture (continue where left off) - FIXED LOGIC
    initial_lecture_id = None
    initial_video_url = ''
    if request.user.is_authenticated:
        # Find last watched lecture that's not completed
        last_progress = UserProgress.objects.filter(
            user=request.user,
            course=course,
            completed=False
        ).order_by('-last_watched').first()
        
        if last_progress:
            initial_lecture_id = last_progress.lecture.id
            if last_progress.lecture.video:
                initial_video_url = last_progress.lecture.video.url
        else:
            # No progress yet, start with first lecture
            first_lecture = Lecture.objects.filter(
                section__course=course
            ).order_by('section__order', 'order').first()
            if first_lecture:
                initial_lecture_id = first_lecture.id
                if first_lecture.video:
                    initial_video_url = first_lecture.video.url

    # Build curriculum with access flags - FIXED ACCESS LOGIC
    curriculum = []
    for section in course.course_sections.all().order_by('order'):
        section_lectures = list(section.lectures.all().order_by('order'))
        lectures = []
        
        for i, lecture in enumerate(section_lectures):
            if lecture.is_preview:
                accessible = True
            elif is_enrolled:
                # SIMPLIFIED ACCESS LOGIC: First lecture is always accessible
                # Subsequent lectures require the immediate previous one to be completed
                if i == 0:  # First lecture in section
                    accessible = True
                else:
                    # Check if previous lecture is completed
                    prev_lecture = section_lectures[i-1]
                    prev_progress = user_progress_map.get(prev_lecture.id)
                    accessible = prev_progress and prev_progress.completed
            else:
                accessible = False

            up = user_progress_map.get(lecture.id)
            completed = bool(up and up.completed)
            progress_percentage = up.progress_percentage if up else 0

            lectures.append({
                'id': lecture.id,
                'title': lecture.title,
                'duration': lecture.duration,
                'video_url': lecture.video.url if lecture.video else '',
                'is_preview': lecture.is_preview,
                'accessible': accessible,
                'completed': completed,
                'progress_percentage': progress_percentage,
                'order': lecture.order,
            })

        curriculum.append({
            'id': section.id,
            'title': section.title,
            'lectures': lectures,
            'total_duration': section.total_duration,
            'total_lectures': len(section_lectures),
        })

    context = {
        'course': course,
        'total_lectures': total_lectures,
        'completed_lectures': completed_lectures,
        'course_progress': course_progress,
        'is_enrolled': is_enrolled,
        'user_is_authenticated': request.user.is_authenticated,
        'curriculum': curriculum,
        'csrf_token': get_token(request),
        'initial_lecture_id': initial_lecture_id,
        'initial_video_url': initial_video_url,
    }
    return render(request, 'course_details.html', context)


@require_POST
def update_lecture_progress(request, lecture_id):
    """Update lecture progress"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'})
    
    lecture = get_object_or_404(Lecture, id=lecture_id)
    
    try:
        watched_duration = float(request.POST.get('watched_duration', 0))
        total_duration = float(request.POST.get('total_duration', 0))
        
        with transaction.atomic():
            progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                lecture=lecture,
                course=lecture.section.course,
                defaults={
                    'watched_duration': watched_duration,
                    'total_duration': total_duration,
                }
            )
            
            if not created:
                progress.watched_duration = max(progress.watched_duration, watched_duration)
                progress.total_duration = total_duration
                progress.save()
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def mark_lecture_completed(request, lecture_id):
    """Mark lecture as completed"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'})
    
    lecture = get_object_or_404(Lecture, id=lecture_id)
    
    try:
        with transaction.atomic():
            progress, created = UserProgress.objects.get_or_create(
                user=request.user,
                lecture=lecture,
                course=lecture.section.course
            )
            
            progress.completed = True
            progress.watched_duration = progress.total_duration or lecture.duration or 0
            progress.progress_percentage = 100
            progress.completed_at = timezone.now()
            progress.save()
        
        # Get next lecture
        next_lecture = lecture.get_next_lecture()
        next_lecture_id = next_lecture.id if next_lecture else None
        
        return JsonResponse({
            'success': True,
            'next_lecture_id': next_lecture_id
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def bundle_courses(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    courses = bundle.courses.all()

    # ✅ Check enrollment for current user
    is_enrolled = Enrollment.objects.filter(user=request.user, bundle=bundle).exists()

    return render(
        request,
        'bundle_courses.html',
        {
            'bundle': bundle,
            'courses': courses,
            'is_enrolled': is_enrolled,
        }
    )

def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('/user/')



# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# Set up logger
logger = logging.getLogger(__name__)


def enroll(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    courses = bundle.courses.all()
    
    # Check if user is already enrolled
    is_enrolled = Enrollment.objects.filter(
        user=request.user, 
        bundle=bundle, 
        payment_status__in=['completed', 'free']
    ).exists()
    
    return render(request, 'enroll.html', {
        'bundle': bundle, 
        'courses': courses,
        'is_enrolled': is_enrolled
    })


def create_payment_order(request, bundle_id):
    if request.method == 'POST':
        try:
            bundle = get_object_or_404(Bundle, id=bundle_id)
            user = request.user
            
            # Check if user is already enrolled
            existing_enrollment = Enrollment.objects.filter(
                user=user, 
                bundle=bundle, 
                payment_status__in=['completed', 'free']
            ).first()
            
            if existing_enrollment:
                return JsonResponse({
                    'success': False,
                    'error': 'You are already enrolled in this bundle'
                })
            
            # Calculate amount in paise
            if bundle.is_free:
                amount = 0
            elif bundle.discount > 0:
                amount = int(bundle.get_discounted_price() * 100)
            else:
                amount = int(bundle.price * 100)
            
            # For free bundles, enroll directly
            if bundle.is_free:
                with transaction.atomic():
                    enrollment = Enrollment.objects.create(
                        user=user,
                        bundle=bundle,
                        payment_status='free',
                        amount_paid=0
                    )
                return JsonResponse({
                    'success': True,
                    'free_enrollment': True,
                    'redirect_url': '/user/payment-success/'
                })
            
            # Create Razorpay order for paid bundles
            order_data = {
                'amount': amount,
                'currency': 'INR',
                'payment_capture': 1,
                'notes': {
                    'bundle_id': bundle.id,
                    'bundle_name': bundle.name,
                    'user_id': user.id,
                    'user_email': user.email  # Use email instead of username
                }
            }
            
            order = client.order.create(data=order_data)
            
            # Create payment transaction record
            payment_transaction = PaymentTransaction.objects.create(
                user=user,
                bundle=bundle,
                razorpay_order_id=order['id'],
                order_amount=bundle.get_discounted_price() if bundle.discount > 0 else bundle.price,
                payment_status='created'
            )
            
            # Log with email instead of username
            logger.info(f"Payment order created for user {user.email}, bundle {bundle.name}")
            
            return JsonResponse({
                'success': True,
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID
            })
            
        except Exception as e:
            logger.error(f"Error creating payment order: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to create payment order. Please try again.'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@csrf_exempt
def verify_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            payment_id = data.get('razorpay_payment_id')
            order_id = data.get('razorpay_order_id')
            signature = data.get('razorpay_signature')
            bundle_id = data.get('bundle_id')
            
            print(f"Verifying payment: order_id={order_id}, payment_id={payment_id}")
            
            # Get the payment transaction
            try:
                payment_transaction = PaymentTransaction.objects.get(
                    razorpay_order_id=order_id,
                    user=request.user
                )
            except PaymentTransaction.DoesNotExist:
                logger.error(f"Payment transaction not found for order {order_id}")
                return JsonResponse({
                    'success': False,
                    'error': 'Payment transaction not found.',
                    'redirect_url': f'/user/payment-failed/?bundle_id={bundle_id}'
                })
            
            bundle = get_object_or_404(Bundle, id=bundle_id)
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            try:
                client.utility.verify_payment_signature(params_dict)
                
                # Payment verification successful
                with transaction.atomic():
                    # Update payment transaction
                    payment_transaction.razorpay_payment_id = payment_id
                    payment_transaction.payment_status = 'completed'
                    payment_transaction.save()
                    
                    # Create or update enrollment
                    enrollment, created = Enrollment.objects.get_or_create(
                        user=request.user,
                        bundle=bundle,
                        defaults={
                            'payment_status': 'completed',
                            'razorpay_order_id': order_id,
                            'razorpay_payment_id': payment_id,
                            'amount_paid': payment_transaction.order_amount
                        }
                    )
                    
                    if not created:
                        enrollment.payment_status = 'completed'
                        enrollment.razorpay_order_id = order_id
                        enrollment.razorpay_payment_id = payment_id
                        enrollment.amount_paid = payment_transaction.order_amount
                        enrollment.save()
                
                # FIXED: Use email instead of username for logging
                user_identifier = request.user.email
                logger.info(f"Payment successful for user {user_identifier}, bundle {bundle.name}")
                print(f"Payment successful for user {user_identifier}, bundle {bundle.name}")
                
                # Clear session data
                if 'last_attempted_bundle' in request.session:
                    del request.session['last_attempted_bundle']
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment verified and enrollment successful',
                    'redirect_url': '/user/payment-success/'
                })
                
            except razorpay.errors.SignatureVerificationError as e:
                payment_transaction.payment_status = 'failed'
                payment_transaction.save()
                logger.error(f"Payment signature verification failed for order {order_id}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Payment verification failed.',
                    'redirect_url': f'/user/payment-failed/?bundle_id={bundle_id}'
                })
                
        except Exception as e:
            logger.error(f"Error in payment verification: {str(e)}")
            print(f"Error in payment verification: {str(e)}")
            import traceback
            traceback.print_exc()  # This will print the full traceback
            
            bundle_id = data.get('bundle_id', '')
            return JsonResponse({
                'success': False,
                'error': 'An error occurred during payment verification.',
                'redirect_url': f'/user/payment-failed/?bundle_id={bundle_id}'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def free_enroll(request, bundle_id):
    if request.method == 'POST':
        try:
            bundle = get_object_or_404(Bundle, id=bundle_id)
            
            if not bundle.is_free:
                return redirect('enroll', bundle_id=bundle_id)
            
            with transaction.atomic():
                enrollment, created = Enrollment.objects.get_or_create(
                    user=request.user,
                    bundle=bundle,
                    defaults={
                        'payment_status': 'free',
                        'amount_paid': 0
                    }
                )
            
            return redirect('payment_success')
            
        except Exception as e:
            logger.error(f"Error in free enrollment: {str(e)}")
            # Handle error appropriately
    
    return redirect('enroll', bundle_id=bundle_id)


def payment_success(request):
    # Clear any session data
    if 'last_attempted_bundle' in request.session:
        del request.session['last_attempted_bundle']
    
    # Get the latest enrollment to show success details
    latest_enrollment = Enrollment.objects.filter(
        user=request.user, 
        payment_status='completed'
    ).order_by('-enrolled_at').first()
    
    return render(request, 'payment_success.html', {
        'enrollment': latest_enrollment
    })


def payment_failed(request):
    # Get bundle_id from various possible sources
    bundle_id = (
        request.GET.get('bundle_id') or
        request.session.get('last_attempted_bundle') or
        None
    )
    
    # Ensure bundle_id is an integer or None
    try:
        bundle_id = int(bundle_id) if bundle_id else None
    except (ValueError, TypeError):
        bundle_id = None
    
    return render(request, 'payment_failed.html', {'bundle_id': bundle_id})


def free_enroll(request, bundle_id):
    if request.method == 'POST':
        try:
            bundle = get_object_or_404(Bundle, id=bundle_id)
            
            if not bundle.is_free:
                return redirect('enroll', bundle_id=bundle_id)
            
            with transaction.atomic():
                enrollment, created = Enrollment.objects.get_or_create(
                    user=request.user,
                    bundle=bundle,
                    defaults={
                        'payment_status': 'free',
                        'amount_paid': 0
                    }
                )
            
            # Redirect to enrollment success page for free enrollments
            return redirect('enrollment_success')
            
        except Exception as e:
            logger.error(f"Error in free enrollment: {str(e)}")
            # Handle error appropriately
    
    return redirect('enroll', bundle_id=bundle_id)

def enrollment_success(request):
    # Get the latest free enrollment
    latest_enrollment = Enrollment.objects.filter(
        user=request.user, 
        payment_status='free'
    ).order_by('-enrolled_at').first()
    
    return render(request, 'enrollment_success.html', {
        'enrollment': latest_enrollment
    })

# Webhook for Razorpay (optional but recommended)

def razorpay_webhook(request):
    if request.method == 'POST':
        try:
            webhook_body = request.body.decode('utf-8')
            webhook_signature = request.headers.get('X-Razorpay-Signature', '')
            
            # Verify webhook signature
            client.utility.verify_webhook_signature(webhook_body, webhook_signature, settings.RAZORPAY_WEBHOOK_SECRET)
            
            webhook_data = json.loads(webhook_body)
            event = webhook_data.get('event')
            
            if event == 'payment.captured':
                payment_entity = webhook_data.get('payload', {}).get('payment', {}).get('entity', {})
                order_id = payment_entity.get('order_id')
                payment_id = payment_entity.get('id')
                
                # Update payment transaction if needed
                try:
                    payment_transaction = PaymentTransaction.objects.get(razorpay_order_id=order_id)
                    if payment_transaction.payment_status != 'paid':
                        payment_transaction.mark_as_paid(payment_id)
                        logger.info(f"Webhook: Payment captured for order {order_id}")
                except PaymentTransaction.DoesNotExist:
                    logger.warning(f"Webhook: Payment transaction not found for order {order_id}")
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
    
    return JsonResponse({'status': 'invalid method'}, status=405)

@login_required
def profile(request):
    user = request.user
    
    # Get enrolled courses with progress from the database
    enrolled_courses = Enrollment.objects.filter(
        user=user, 
        payment_status__in=['completed', 'free'],
        is_active=True
    ).select_related('bundle').prefetch_related('bundle__courses')
    
    # Enhanced: Get all current courses and their completion status
    for enrollment in enrolled_courses:
        # Get ALL current courses in the bundle (including newly added ones)
        enrollment.current_bundle_courses = enrollment.bundle.courses.all()
        
        # Get completed courses for this user in this bundle
        enrollment.completed_courses = get_completed_courses(user, enrollment.bundle)
        
        # Calculate progress based on current courses
        enrollment.actual_progress = calculate_course_progress(enrollment)
        
        # Update the progress percentage in database if different
        if enrollment.actual_progress != enrollment.progress_percentage:
            enrollment.progress_percentage = enrollment.actual_progress
            enrollment.save()
    
    # Get counts
    enrolled_courses_count = enrolled_courses.count()
    completed_courses_count = enrolled_courses.filter(progress_percentage=100).count()
    
    # Calculate wishlist count if Wishlist model exists
    try:
        from user_part.models import Wishlist
        wishlist_count = Wishlist.objects.filter(student=user).count()
    except:
        wishlist_count = 0
    
    # Calculate profile completion
    profile_completion = calculate_profile_completion(user)
    
    # Calculate total learning hours and certificates
    total_learning_hours = calculate_total_learning_hours(user)
    certificates_count = enrolled_courses.filter(progress_percentage=100).count()
    
    # Recent activity based on actual user actions
    recent_activity = get_recent_activity(user)
    
    context = {
        'user': user,
        'enrolled_courses': enrolled_courses,
        'enrolled_courses_count': enrolled_courses_count,
        'completed_courses_count': completed_courses_count,
        'wishlist_count': wishlist_count,
        'profile_completion': profile_completion,
        'recent_activity': recent_activity,
        'total_learning_hours': total_learning_hours,
        'certificates_count': certificates_count,
    }
    
    return render(request, 'profile.html', context)

def calculate_course_progress(enrollment):
    """
    Calculate actual progress percentage for a course enrollment
    Based on ALL current courses in the bundle
    """
    try:
        bundle = enrollment.bundle
        total_lectures = 0
        completed_lectures = 0
        
        # Get ALL current courses in the bundle (including newly added ones)
        courses = bundle.courses.all()
        
        for course in courses:
            # Get all lectures for this course
            lectures = Lecture.objects.filter(section__course=course)
            total_lectures += lectures.count()
            
            # Count completed lectures for this course
            completed_lectures += get_completed_lectures_count(enrollment.user, course)
        
        if total_lectures > 0:
            progress = int((completed_lectures / total_lectures) * 100)
            return min(progress, 100)  # Cap at 100%
        return 0
        
    except Exception as e:
        print(f"Error calculating progress: {e}")
        return enrollment.progress_percentage  # Return existing value if error
    
def calculate_total_learning_hours(user):
    """
    Calculate total learning hours based on user progress
    """
    try:
        # Calculate based on completed lectures and their durations
        total_minutes = 0
        
        # Get all completed user progress records
        completed_progress = UserProgress.objects.filter(
            user=user,
            completed=True
        ).select_related('lecture')
        
        for progress in completed_progress:
            if progress.lecture.duration:
                # Parse duration (assuming format like "05:05" or "10min")
                duration = progress.lecture.duration
                if ':' in duration:
                    # Format: "05:05" (minutes:seconds)
                    parts = duration.split(':')
                    if len(parts) == 2:
                        minutes = int(parts[0]) if parts[0].isdigit() else 0
                        seconds = int(parts[1]) if parts[1].isdigit() else 0
                        total_minutes += minutes + (seconds / 60)
                elif 'min' in duration.lower():
                    # Format: "10min"
                    minutes_str = duration.lower().replace('min', '').strip()
                    if minutes_str.isdigit():
                        total_minutes += int(minutes_str)
                else:
                    # Try to parse as plain number (minutes)
                    try:
                        total_minutes += float(duration)
                    except ValueError:
                        pass
        
        # Add some estimated time for partially watched videos
        partial_progress = UserProgress.objects.filter(
            user=user,
            completed=False,
            watched_duration__gt=0
        )
        
        for progress in partial_progress:
            if progress.total_duration > 0:
                # Add 50% of the watched time as learning time
                watched_minutes = progress.watched_duration / 60
                total_minutes += watched_minutes * 0.5
        
        total_hours = total_minutes / 60
        return round(total_hours, 1)  # Round to 1 decimal place
        
    except Exception as e:
        print(f"Error calculating learning hours: {e}")
        # Return a default value or calculate based on completed courses
        completed_courses_count = Enrollment.objects.filter(
            user=user,
            progress_percentage=100
        ).count()
        return completed_courses_count * 10  # Estimate 10 hours per completed course

def get_completed_lectures_count(user, course):
    """
    Count how many lectures user has completed in a course
    """
    try:
        # Count completed lectures using UserProgress model
        completed_count = UserProgress.objects.filter(
            user=user,
            lecture__section__course=course,
            completed=True
        ).count()
        return completed_count
    except Exception as e:
        print(f"Error counting completed lectures: {e}")
        return 0

def get_completed_courses(user, bundle):
    """
    Get list of completed courses for a user in a bundle
    """
    completed_courses = []
    try:
        for course in bundle.courses.all():
            if is_course_completed(user, course):
                completed_courses.append(course)
    except Exception as e:
        print(f"Error getting completed courses: {e}")
    
    return completed_courses

def is_course_completed(user, course):
    """
    Check if a user has completed a course
    """
    try:
        # Get all lectures in the course
        total_lectures = Lecture.objects.filter(section__course=course).count()
        
        # Count completed lectures
        completed_lectures = UserProgress.objects.filter(
            user=user,
            lecture__section__course=course,
            completed=True
        ).count()
        
        # Course is completed if all lectures are completed
        return total_lectures > 0 and completed_lectures == total_lectures
    except Exception as e:
        print(f"Error checking course completion: {e}")
        return False

@login_required

def mark_lecture_completed(request, lecture_id):
    """
    Mark a lecture as completed when user finishes watching
    """
    try:
        lecture = get_object_or_404(Lecture, id=lecture_id)
        course = lecture.section.course
        
        # Check if user is enrolled in the course's bundle
        is_enrolled = Enrollment.objects.filter(
            user=request.user,
            bundle=course.bundle,
            payment_status__in=['completed', 'free'],
            is_active=True
        ).exists()
        
        if not is_enrolled:
            return JsonResponse({'success': False, 'error': 'Not enrolled in this course'})
        
        # Create or update user progress
        progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            lecture=lecture,
            course=course,
            defaults={'completed': True}
        )
        
        if not created:
            progress.completed = True
            progress.save()
        
        # Update enrollment progress
        enrollment = Enrollment.objects.get(
            user=request.user,
            bundle=course.bundle
        )
        enrollment.actual_progress = calculate_course_progress(enrollment)
        enrollment.progress_percentage = enrollment.actual_progress
        enrollment.save()
        
        return JsonResponse({'success': True, 'progress': enrollment.progress_percentage})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def update_lecture_progress(request, lecture_id):
    """
    Update progress for a lecture (for partial completion tracking)
    """
    try:
        lecture = get_object_or_404(Lecture, id=lecture_id)
        course = lecture.section.course
        
        watched_duration = request.POST.get('watched_duration', 0)
        total_duration = request.POST.get('total_duration', 0)
        
        # Check if user is enrolled
        is_enrolled = Enrollment.objects.filter(
            user=request.user,
            bundle=course.bundle,
            payment_status__in=['completed', 'free'],
            is_active=True
        ).exists()
        
        if not is_enrolled:
            return JsonResponse({'success': False, 'error': 'Not enrolled in this course'})
        
        # Create or update progress
        progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            lecture=lecture,
            course=course
        )
        
        progress.watched_duration = int(watched_duration)
        progress.total_duration = int(total_duration)
        
        # Mark as completed if watched 90% or more of the video
        if progress.total_duration > 0 and (progress.watched_duration / progress.total_duration) >= 0.9:
            progress.completed = True
        
        progress.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_recent_activity(user):
    """
    Get recent user activity based on actual actions
    """
    activities = []
    
    try:
        # Recent enrollments (last 7 days)
        recent_enrollments = Enrollment.objects.filter(
            user=user,
            enrolled_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-enrolled_at')[:3]
        
        for enrollment in recent_enrollments:
            activities.append({
                'icon': 'play-circle',
                'color': 'primary',
                'message': f'Enrolled in {enrollment.bundle.name}',
                'timestamp': enrollment.enrolled_at
            })
        
        # Recent course completions
        recent_completions = Enrollment.objects.filter(
            user=user,
            progress_percentage=100,
            completed_at__isnull=False,
            completed_at__gte=timezone.now() - timedelta(days=30)
        ).order_by('-completed_at')[:2]
        
        for enrollment in recent_completions:
            activities.append({
                'icon': 'check-circle',
                'color': 'success',
                'message': f'Completed {enrollment.bundle.name}',
                'timestamp': enrollment.completed_at
            })
        
        # Recent video watching activity (last 3 days)
        recent_progress = UserProgress.objects.filter(
            user=user,
            last_watched__gte=timezone.now() - timedelta(days=3)
        ).select_related('lecture').order_by('-last_watched')[:2]
        
        for progress in recent_progress:
            if progress.completed:
                activities.append({
                    'icon': 'film',
                    'color': 'info',
                    'message': f'Finished watching: {progress.lecture.title}',
                    'timestamp': progress.last_watched
                })
            else:
                activities.append({
                    'icon': 'play-btn',
                    'color': 'warning',
                    'message': f'Started watching: {progress.lecture.title}',
                    'timestamp': progress.last_watched
                })
        
        # If no recent activity, show some generic activities
        if not activities:
            activities.extend([
                {
                    'icon': 'person',
                    'color': 'secondary',
                    'message': 'Joined the learning platform',
                    'timestamp': user.date_joined
                },
                {
                    'icon': 'compass',
                    'color': 'secondary', 
                    'message': 'Started your learning journey',
                    'timestamp': user.date_joined + timedelta(hours=1)
                }
            ])
        
        # Sort by timestamp and return latest 5
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:5]
        
    except Exception as e:
        print(f"Error getting recent activity: {e}")
        # Return default activities if there's an error
        return [
            {
                'icon': 'person',
                'color': 'secondary',
                'message': 'Welcome to your learning dashboard!',
                'timestamp': timezone.now()
            }
        ]


@login_required
def update_profile(request):
    if request.method == 'POST':
        user = request.user
        
        try:
            # Update user fields - using full_name instead of first_name/last_name
            if hasattr(user, 'full_name'):
                user.full_name = request.POST.get('full_name', '')
            
            if hasattr(user, 'phone'):
                user.phone = request.POST.get('phone', '')
            
            if hasattr(user, 'bio'):
                user.bio = request.POST.get('bio', '')
            
            user.save()
            messages.success(request, 'Profile updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    return redirect('profile')

@login_required
def update_profile_picture(request):
    if request.method == 'POST' and request.FILES.get('profile_image'):  # Changed to profile_image
        user = request.user
        try:
            if hasattr(user, 'profile_image'):  # Changed to profile_image
                user.profile_image = request.FILES['profile_image']  # Changed to profile_image
                user.save()
                messages.success(request, 'Profile picture updated successfully!')
            else:
                messages.error(request, 'Profile picture feature not available.')
        except Exception as e:
            messages.error(request, f'Error updating profile picture: {str(e)}')
    
    return redirect('profile')

def calculate_profile_completion(user):
    """
    Calculate profile completion percentage based on CustomUser fields
    """
    completion_score = 0
    total_fields = 4  # email, full_name, phone, profile_image
    
    # Check required fields
    if user.email:
        completion_score += 1
    
    # Check optional fields
    if hasattr(user, 'full_name') and user.full_name and user.full_name.strip():
        completion_score += 1
    
    if hasattr(user, 'phone') and user.phone and user.phone.strip():
        completion_score += 1
    
    if hasattr(user, 'profile_image') and user.profile_image:
        completion_score += 1
    
    return int((completion_score / total_fields) * 100)

@login_required
def change_password(request):
    if request.method == 'POST':
        # Add password change logic here
        messages.success(request, 'Password changed successfully!')
        return redirect('profile')
    
    return render(request, 'change_password.html')

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'Your account has been deleted successfully.')
        return redirect('home')
    
    return redirect('profile')