from django.urls import path
from . import views

urlpatterns = [
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin_login/', views.admin_login, name='admin_login'),
    path('admin_logout/', views.admin_logout, name='admin_logout'),
    path('bundles/', views.bundles, name='bundles'),
    path('delete-bundle/<int:bundle_id>/', views.delete_bundle, name='delete_bundle'),
    path('edit-bundle/<int:bundle_id>/', views.edit_bundle, name='edit_bundle'),
    path('add_bundle/',views.add_bundle,name="add_bundle"),
    path('add_course/', views.add_course, name='add_course'),
    path('view_courses/', views.view_courses, name='view_courses'),
    path('edit_course/<int:course_id>/', views.edit_course, name='edit_course'),
    path('course_detail/<int:course_id>/', views.course_detail, name='course_detail'),
    path('delete_course/<int:course_id>/', views.delete_course, name='delete_course'),
    path('add_section/<int:course_id>/', views.add_section, name='add_section'),
    path('edit_section/<int:section_id>/', views.edit_section, name='edit_section'),
    path('delete_section/<int:section_id>/', views.delete_section, name='delete_section'),
    path('add_lecture/<int:section_id>/', views.add_lecture, name='add_lecture'),
    path('edit_lecture/<int:lecture_id>/', views.edit_lecture, name='edit_lecture'),
    path('delete_lecture/<int:lecture_id>/', views.delete_lecture, name='delete_lecture'),



    # session urls
    path('admin_live_sessions/', views.admin_live_sessions, name='admin_live_sessions'),
    path('add_live_session/', views.add_live_session, name='add_live_session'),
    path('edit_live_session/<int:session_id>/', views.edit_live_session, name='edit_live_session'),
    path('delete_live_session/<int:session_id>/', views.delete_live_session, name='delete_live_session'),
    

    #zoom urls
    path('live-sessions/', views.live_session_test, name='live_session_test'),
    path('create-live-session/', views.create_live_session, name='create_live_session'),
    path('test-zoom-connection/', views.test_zoom_connection, name='test_zoom_connection'),
    path('delete-session/<int:session_id>/', views.delete_live_session, name='delete_live_session'),
]
