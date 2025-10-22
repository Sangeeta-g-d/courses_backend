from django.db import models
from django.conf import settings
from django.utils.text import slugify

# ---------------------------------------------------------
# CATEGORY MODEL (e.g., Development, Business, Design)
# ---------------------------------------------------------
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Category, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


# ---------------------------------------------------------
# INSTRUCTOR MODEL (details about instructors)
# ---------------------------------------------------------
class Instructor(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=255)
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='instructors/', blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)

    # Separate social media fields
    linkedin = models.URLField(max_length=255, blank=True, null=True)
    youtube = models.URLField(max_length=255, blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)
    

    def __str__(self):
        return self.full_name



# ---------------------------------------------------------
# COURSE MODEL (main model)
# ---------------------------------------------------------


class Course(models.Model):
    instructor = models.ForeignKey('Instructor', on_delete=models.CASCADE, related_name='courses')
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='courses')

    title = models.CharField(max_length=1000)
    slug = models.SlugField(unique=True, blank=True)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    preview_video = models.FileField(upload_to='course_videos/', blank=True, null=True, help_text="Upload a short preview video")

    short_description = models.TextField(max_length=2000)
    full_description = models.TextField()

    language = models.CharField(max_length=1000, default='English')
    level = models.CharField(max_length=500, choices=[
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced')
    ], default='Beginner')

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.PositiveIntegerField(default=0)  # percentage
    is_free = models.BooleanField(default=False)

    # ✅ Single column for “This course includes”
    course_includes = models.TextField(
        blank=True, null=True,
        help_text="Add course features separated by commas (e.g. '31.5 hours on-demand video, 131 coding exercises, 93 articles')"
    )

    requirements = models.TextField(blank=True, null=True)
    learning_outcomes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super(Course, self).save(*args, **kwargs)

    def get_discounted_price(self):
        if self.discount > 0:
            return self.price - (self.price * self.discount / 100)
        return self.price

    def get_course_includes_list(self):
        """Return includes as a clean list for template display."""
        if self.course_includes:
            return [item.strip() for item in self.course_includes.split(',')]
        return []

    def __str__(self):
        return self.title
    


class CourseSection(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='course_sections')  # changed here
    title = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    total_lectures = models.PositiveIntegerField(default=0)
    total_duration = models.CharField(max_length=300, blank=True, null=True, help_text="Example: 19min or 2h 15min")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lecture(models.Model):
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, related_name='lectures')
    title = models.CharField(max_length=500)
    duration = models.CharField(max_length=500, blank=True, null=True, help_text="Example: 05:05 or 10min")
    video = models.FileField(upload_to='lectures/videos/', blank=True, null=True)
    is_preview = models.BooleanField(default=False)
    resource = models.FileField(upload_to='lectures/resources/', blank=True, null=True)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.section.title} - {self.title}"




# ---------------------------------------------------------
# SECTION MODEL (each course can have multiple sections)
# ---------------------------------------------------------
class Section(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections_old')  # changed here
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


# ---------------------------------------------------------
# LESSON MODEL (each section can have multiple lessons/videos)
# ---------------------------------------------------------
class Lesson(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    video_url = models.URLField(blank=True, null=True)
    video_file = models.FileField(upload_to='course_videos/', blank=True, null=True)
    duration = models.CharField(max_length=20, blank=True, null=True)
    is_preview = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.section.title} - {self.title}"


# ---------------------------------------------------------
# ENROLLMENT MODEL (student course enrollment)
# ---------------------------------------------------------
class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} enrolled in {self.course.title}"


# ---------------------------------------------------------
# COURSE REVIEW MODEL
# ---------------------------------------------------------
class Review(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(default=1)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course.title} - {self.rating}⭐"


# ---------------------------------------------------------
# WISHLIST MODEL
# ---------------------------------------------------------
class Wishlist(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"


# ---------------------------------------------------------
# TAGS MODEL (optional - for search/filter)
# ---------------------------------------------------------
class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    courses = models.ManyToManyField(Course, related_name='tags', blank=True)

    def __str__(self):
        return self.name
