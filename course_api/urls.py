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
    path("lectures/<int:section_id>/",SectionLectureListAPIView.as_view(),name="section-lectures"),
    path("update-progress/",UpdateUserProgressAPIView.as_view(),name="update-user-progress"),

    path('user-rankings/', DashboardRankingAPIView.as_view()),
    path('courses-list/',CourseListAPIView.as_view(),name='courses-list'),
    path('enrolled-bundles/',EnrolledBundleListAPIView.as_view(),name='enrolled-bundles'),
    path('profile-stats/',UserProfileStatsAPIView.as_view(),name='user-profile-stats'),
    path('continue-learning/', ContinueLearningAPIView.as_view(), name='continue-learning'),

    path("posts/", PostListAPIView.as_view(), name="post-list"),
    path("posts/<int:post_id>/toggle-like/", TogglePostLikeAPIView.as_view(), name="toggle-post-like"),
]
