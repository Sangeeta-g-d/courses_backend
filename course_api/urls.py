from django.urls import path
from . import views
from . views import *

urlpatterns = [
    path("bundles/", PublishedBundleListAPIView.as_view(), name="published-bundles"),
]
