"""
URL configuration for stixify project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from .web.more_views import txt2stix, profile
from .web.arango_based_views import arango_views
from .web.views import FileView, GroupingView, JobView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.conf.urls.static import static

API_VERSION = "v1"

router = routers.SimpleRouter(use_regex_path=False)
# profile view
router.register('profiles', profile.ProfileView, 'profile-view')
router.register('files', FileView, 'files-view')
router.register('grouping', GroupingView, 'grouping-view')
router.register('jobs/reports', arango_views.ReportView, 'report-view')
router.register('jobs', JobView, 'job-view')
router.register('objects', arango_views.ObjectsView, 'object-view')
# txt2stix views
router.register('extractors', txt2stix.ExtractorsView, "extractors-view")
router.register('whitelists', txt2stix.WhitelistsView, "whitelists-view")
router.register('aliases', txt2stix.AliasesView, "aliases-view")

urlpatterns = [
    path(f'api/{API_VERSION}/', include(router.urls)),
    path('admin/', admin.site.urls),
    # YOUR PATTERNS
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]


urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
