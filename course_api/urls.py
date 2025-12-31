from django.urls import path
from . import views
from . views import *

urlpatterns = [
    path("bundles/", BundleListAPIView.as_view(), name="published-bundles"),
]
