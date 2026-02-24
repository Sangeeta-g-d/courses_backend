"""
URL configuration for courses_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from user_part.views import page_not_found

urlpatterns = [
    path('admin/', admin.site.urls),
    path('backend/', include('admin_part.urls')),   # 👈 Add this line
    path('', include('user_part.urls')),  # 👈 Add this line


    # API URLs
    path('api/auth/', include('auth_app.urls')),
    path('api/courses/', include('course_api.urls')),
    
    # Catch-all pattern for 404 (must be last)
    re_path(r'^.*/$', page_not_found),
    re_path(r'^.*$', page_not_found),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 handler (for when DEBUG = False)
handler404 = page_not_found

