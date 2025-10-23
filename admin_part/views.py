from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import Category,Instructor,Course
from django.utils.text import slugify
from django.contrib.auth import logout
import json
from django.http import JsonResponse
# Create your views here.


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
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid credentials or not an admin user.")
    return render(request, 'admin_login.html')


def category_form(request):
    if request.method == "POST":
        name = request.POST.get('name')
        if not name:
            messages.error(request, "Please enter a category name.")
            return redirect('category_form')
        # Check if category already exists
        if Category.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This category already exists.")
            return redirect('category_form')
        # Create new category
        Category.objects.create(name=name)
        messages.success(request, "Category added successfully!")
        return redirect('category_form')
    
    # Get recent categories for display
    recent_categories = Category.objects.all().order_by('-id')[:5]
    
    context = {
        'recent_categories': recent_categories
    }
    return render(request, 'category_form.html', context)

def categories(request):
    categories = Category.objects.all().order_by('id')
    return render(request, 'categories.html', {'categories': categories})


def edit_category(request):
    if request.method == "POST":
        category_id = request.POST.get("id")
        name = request.POST.get("name")

        if not category_id or not name:
            messages.error(request, "Missing required fields.")
            return redirect("categories")

        category = get_object_or_404(Category, id=category_id)

        # Check for duplicates (case insensitive, excluding current)
        if Category.objects.filter(name__iexact=name).exclude(id=category_id).exists():
            messages.error(request, "Category with this name already exists.")
        else:
            category.name = name
            category.slug = slugify(name)
            category.save()
            messages.success(request, "Category updated successfully!")

    return redirect("categories")


def delete_category(request, id):
    if request.method == 'POST':
        category = get_object_or_404(Category, id=id)
        category.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

 


def instructor_form(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')
        bio = request.POST.get('bio')
        designation = request.POST.get('designation')
        profile_image = request.FILES.get('profile_image')

        linkedin = request.POST.get('linkedin')
        website = request.POST.get('website')
        
        youtube = request.POST.get('youtube')

        # Check if email already exists
        if Instructor.objects.filter(email=email).exists():
            messages.error(request, "An instructor with this email already exists.")
            return redirect('instructor_form')

        # Create instructor
        Instructor.objects.create(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            password=password,  # (Later you can hash this)
            bio=bio,
            designation=designation,
            profile_image=profile_image,
            linkedin=linkedin,
            website=website,
            youtube=youtube
        )

        messages.success(request, f"Instructor '{full_name}' added successfully!")
        return redirect('instructor_form')

    recent_instructors = Instructor.objects.all().order_by('-id')[:5]
    return render(request, 'instructor_form.html', {'recent_instructors': recent_instructors})

def instructors(request):
    instructor_list = Instructor.objects.all().order_by('-id')  # latest first
    return render(request, 'instructors.html', {'instructor_list': instructor_list})

def instructor_edit(request, instructor_id):
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    if request.method == 'POST':
        instructor.full_name = request.POST.get('full_name')
        instructor.email = request.POST.get('email')
        instructor.phone_number = request.POST.get('phone_number')
        instructor.designation = request.POST.get('designation')
        instructor.bio = request.POST.get('bio')
        instructor.linkedin = request.POST.get('linkedin')
        instructor.youtube = request.POST.get('youtube')
        instructor.website = request.POST.get('website')

        profile_image = request.FILES.get('profile_image')
        if profile_image:
            instructor.profile_image = profile_image
        
        instructor.save()
        # Optionally, add a success message here
        return redirect('instructors')
    
    return render(request, 'instructor_edit.html', {'instructor': instructor})


def delete_instructor(request, pk):
    if request.method == "POST":
        instructor = get_object_or_404(Instructor, pk=pk)
        instructor.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)

def course_form(request):
    instructors = Instructor.objects.all()
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
            instructor = Instructor.objects.get(id=instructor_id)
            category = Category.objects.get(id=category_id)

            course = Course.objects.create(
                instructor=instructor,
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

        except Instructor.DoesNotExist:
            messages.error(request, "Invalid instructor selected.")
        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
        except Exception as e:
            messages.error(request, f"Something went wrong: {str(e)}")

        return redirect('course_form')

    return render(request, 'course_form.html', {
        'instructors': instructors,
        'categories': categories,
    })


def course_list(request):
    courses = Course.objects.all().select_related('instructor', 'category')
    return render(request, 'course_list.html', {'courses': courses})
