from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/',views.user_login,name='user_login'),
    path('register/',views.register,name='register'),
    path('user_details/', views.user_details, name='user_details'),
    path('course_details/<int:course_id>/', views.course_details, name='course_details'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('bundle/<int:bundle_id>/', views.bundle_courses, name='bundle_courses'),

]