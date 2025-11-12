from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.utils import timezone
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------
# CATEGORY MODEL (e.g., Development, Business, Design)
# ---------------------------------------------------------
class Bundle(models.Model):  # Keep table name the same
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    # Pricing moves here
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.PositiveIntegerField(default=0)
    is_free = models.BooleanField(default=False)

    short_description = models.TextField(max_length=2000, blank=True, null=True)
    full_description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to='bundle_thumbnails/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Bundle"
        verbose_name_plural = "Bundles"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        # Auto-set free logic
        if self.is_free:
            self.price = 0
            self.discount = 0

        super().save(*args, **kwargs)

    def get_discounted_price(self):
        if self.discount > 0 and not self.is_free:
            return self.price - (self.price * self.discount / 100)
        return self.price

    def __str__(self):
        return self.name


# ---------------------------------------------------------
# COURSE MODEL (main model)
# ---------------------------------------------------------

class Course(models.Model):
    # Bundle reference
    bundle = models.ForeignKey('Bundle', on_delete=models.SET_NULL, null=True, related_name='courses')

    title = models.CharField(max_length=1000)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    preview_video = models.FileField(upload_to='course_videos/', blank=True, null=True)

    short_description = models.TextField(max_length=2000)
    full_description = models.TextField()

    language = models.CharField(max_length=1000, default='English')
    level = models.CharField(
        max_length=500,
        choices=[
            ('Beginner', 'Beginner'),
            ('Intermediate', 'Intermediate'),
            ('Advanced', 'Advanced')
        ],
        default='Beginner'
    )

    course_includes = models.TextField(
        blank=True, null=True,
        help_text="Add course features separated by commas (e.g. '31.5 hours on-demand video, 131 coding exercises, 93 articles')"
    )
    requirements = models.TextField(blank=True, null=True)
    learning_outcomes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)

    def get_course_includes_list(self):
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

    def get_next_lecture(self):
        """Get the next lecture in the same section"""
        try:
            return Lecture.objects.filter(
                section=self.section,
                order__gt=self.order
            ).order_by('order').first()
        except Exception:
            return None

# ---------------------------------------------------------
# ENROLLMENT MODEL (student course enrollment)
# ---------------------------------------------------------


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



class LiveSession(models.Model):
    title = models.CharField(max_length=255)
    agenda = models.TextField()
    thumbnail = models.ImageField(upload_to='live_sessions/thumbnails/')
    meeting_number = models.CharField(max_length=50, blank=True, null=True)
    Passcode = models.CharField(max_length=20, blank=True, null=True)
    meeting_url = models.CharField(max_length=800, blank=True, null=True)
    session_date = models.DateField()
    session_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        """
        Return True if current IST time is between 5 minutes before start
        and 60 minutes after start.
        """
        ist = ZoneInfo("Asia/Kolkata")
        session_datetime = datetime.combine(self.session_date, self.session_time).replace(tzinfo=ist)
        now_ist = timezone.now().astimezone(ist)
        return (session_datetime - timedelta(minutes=5)) <= now_ist <= (session_datetime + timedelta(minutes=60))

    def __str__(self):
        return self.title
# ---------------------------------------------------------
# PAYMENT MODELS
# ---------------------------------------------------------
class Enrollment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('free', 'Free'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    bundle = models.ForeignKey('Bundle', on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    
    # Payment Information
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Progress Tracking
    progress_percentage = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Razorpay Details
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    # Additional Fields
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'bundle')
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.user.username} - {self.bundle.name}"

    def save(self, *args, **kwargs):
        # Set completed_at when progress reaches 100%
        if self.progress_percentage == 100 and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def update_progress(self):
        """Method to update progress percentage"""
        # Your progress calculation logic here
        total_lectures = 0
        completed_lectures = 0
        
        courses = self.bundle.courses.all()
        for course in courses:
            course_lectures = Lecture.objects.filter(section__course=course).count()
            total_lectures += course_lectures
            # Add your completion logic here
        
        if total_lectures > 0:
            self.progress_percentage = int((completed_lectures / total_lectures) * 100)
            self.save()

class PaymentTransaction(models.Model):
    TRANSACTION_STATUS_CHOICES = [
        ('created', 'Created'),
        ('attempted', 'Attempted'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # User and Bundle Info
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_transactions')
    bundle = models.ForeignKey('Bundle', on_delete=models.CASCADE, related_name='payment_transactions')
    
    # Razorpay Order Details
    razorpay_order_id = models.CharField(max_length=255, unique=True)
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    
    # Payment Details
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='created')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_date = models.DateTimeField(blank=True, null=True)
    
    # Additional Info
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)  # Store additional payment data

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['razorpay_order_id']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.bundle.name} - {self.razorpay_order_id}"

    def mark_as_paid(self, payment_id, payment_date=None):
        self.razorpay_payment_id = payment_id
        self.payment_status = 'paid'
        self.payment_date = payment_date or timezone.now()
        self.save()

    def mark_as_failed(self, error_message):
        self.payment_status = 'failed'
        self.error_message = error_message
        self.save()


class Refund(models.Model):
    REFUND_STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('processed', 'Processed'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='refunds')
    razorpay_refund_id = models.CharField(max_length=255, blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='requested')
    reason = models.TextField()
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Refund for {self.enrollment} - {self.refund_amount}"
    

class UserProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress')
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='user_progress')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='user_progress')
    completed = models.BooleanField(default=False)
    watched_duration = models.PositiveIntegerField(default=0)  # in seconds
    total_duration = models.PositiveIntegerField(default=0)    # in seconds
    last_watched = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lecture')
        verbose_name_plural = "User Progress"

    def __str__(self):
        return f"{self.user.email} - {self.lecture.title} - {'Completed' if self.completed else 'In Progress'}"

    def save(self, *args, **kwargs):
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)