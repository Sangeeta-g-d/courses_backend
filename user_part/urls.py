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
    path('logout/', views.logout_view, name='user_logout'),


    path('enroll/<int:bundle_id>/', views.enroll, name='enroll'),
    path('create-payment-order/<int:bundle_id>/', views.create_payment_order, name='create_payment_order'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    path('free-enroll/<int:bundle_id>/', views.free_enroll, name='free_enroll'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('enrollment-success/', views.enrollment_success, name='enrollment_success'),
    path('payment-failed/', views.payment_failed, name='payment_failed'),
    path('razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),


    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/update-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/delete-account/', views.delete_account, name='delete_account'),


    path('user/update-lecture-progress/<int:lecture_id>/', views.update_lecture_progress, name='update_lecture_progress'),
    path('user/mark-lecture-completed/<int:lecture_id>/', views.mark_lecture_completed, name='mark_lecture_completed'),

    path('meetings/', views.meetings, name='meetings'),
    path('join_live_session_user/<int:session_id>/', views.join_live_session_user, name='join_live_session_user'),
    path('zoom_signature/', views.zoom_sdk_signature, name='zoom_sdk_signature'),
]