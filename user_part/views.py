from django.shortcuts import render, get_object_or_404, redirect
from admin_part.models import Course, CourseSection, Lecture,Bundle
from auth_app.models import CustomUser, UserProfile
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout

# Create your views here.


def home(request):
    return render(request, 'home.html')


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
    return render(request, 'dashboard.html',{'bundles': bundles})


def course_details(request, course_id):
    # Get the course with all related sections and lectures
    course = get_object_or_404(
        Course.objects.prefetch_related(
            'course_sections__lectures'
        ),
        id=course_id
    )
    
    # Calculate total lectures
    total_lectures = 0
    for section in course.course_sections.all():
        total_lectures += section.lectures.count()
    
    context = {
        'course': course,
        'total_lectures': total_lectures,
    }
    
    return render(request, 'course_details.html', context)

def bundle_courses(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    courses = bundle.courses.all()  # ✅ Fetch queryset
    return render(request, 'bundle_courses.html', {'bundle': bundle, 'courses': courses})