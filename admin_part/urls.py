from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('admin_login/', views.admin_login, name='admin_login'),
    path('admin_logout', views.admin_logout, name='admin_logout'),
    path('category_form', views.category_form, name='category_form'),
    path('categories/', views.categories, name='categories'),
    path('edit_category', views.edit_category, name='category_edit'),
    path('delete_category/<int:id>/', views.delete_category, name='delete_category'),
    path('course_form', views.course_form, name='course_form'),
    path('instructor_form', views.instructor_form, name='instructor_form'),
    path('instructors', views.instructors, name='instructors'),
    path('instructor_edit/<int:instructor_id>/', views.instructor_edit, name='instructor_edit'),
    path('delete/<int:pk>/', views.delete_instructor, name='delete_instructor'),
    path('course_list/', views.course_list, name='course_list'),



]
