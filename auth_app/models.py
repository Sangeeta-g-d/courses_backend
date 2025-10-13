from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

# -------------------------------
# Custom User Manager
# -------------------------------
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# -------------------------------
# Custom User Model
# -------------------------------
class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('student', 'Student'),
    )

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # email and password are handled by default

    def __str__(self):
        return self.email
