from django.urls import path
from . import views
from . views import *

urlpatterns = [
    path("bundles/", BundleListAPIView.as_view(), name="published-bundles"),
    path('courses/<int:bundle_id>/',BundleCoursesAPIView.as_view(),name='bundle-courses'),
    path('enroll/<int:bundle_id>/',BundleEnrollAPIView.as_view(),name='bundle-enroll'),
    path('verify-payment/',VerifyRazorpayPaymentAPIView.as_view(),name='verify-enrollment-payment'),
    path('dashboard-api/', HomeFeaturedAPIView.as_view(), name='home-featured'),

    path('course-sections/<int:course_id>/',CourseSectionsAPIView.as_view(),name='course-sections'),
]
