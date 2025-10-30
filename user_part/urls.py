from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('user_course_detail/', views.user_course_detail, name='user_course_detail'),
]