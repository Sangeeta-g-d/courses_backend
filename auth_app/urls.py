from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='register'),
    path('profile-details/', views.UserProfileAPIView.as_view(), name='profile_details'),
    path('user-login/', views.LoginAPIView.as_view(), name='user_login'),
    path('user-profile/', views.FetchUserProfileAPIView.as_view(), name='user_profile'),
    path("live-sessions/", views.LiveSessionListAPIView.as_view(), name="live-session-list"),
    path("live-sessions/<int:session_id>/", views.LiveSessionDetailAPIView.as_view(), name="live-session-detail"),
    path("zoom-token/", views.ZoomTokenGeneratorAPIView.as_view(), name="zoom-token-generator"),
]