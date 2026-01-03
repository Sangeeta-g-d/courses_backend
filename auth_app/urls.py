from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='register'),
    path('profile-details/', views.UserProfileAPIView.as_view(), name='profile_details'),
    path('user-login/', views.LoginAPIView.as_view(), name='user_login'),
]