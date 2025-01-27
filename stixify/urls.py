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
from dogesec_commons.objects import views as arango_views
from dogesec_commons.stixifier.views import ProfileView, ExtractorsView
from .web.views import FileView, DossierView, JobView, ReportView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf.urls.static import static

from django.http import JsonResponse
def handler404(*args, **kwargs):
    return JsonResponse(dict(code=404, message='non-existent page'), status=404)

def handler500(*args, **kwargs):
    return JsonResponse(dict(code=500, message='internal server error'), status=500)


API_VERSION = "v1"

router = routers.SimpleRouter(use_regex_path=True)
# profile view
router.register('profiles', ProfileView, 'profile-view')
router.register('files', FileView, 'file-view')
router.register('dossiers', DossierView, 'dossier-view')
router.register('jobs', JobView, 'job-view')
router.register('reports', ReportView, 'report-view')
# objects
router.register("objects", arango_views.ObjectsWithReportsView, "object-view-orig")
router.register('objects/smos', arango_views.SMOView, "object-view-smo")
router.register('objects/scos', arango_views.SCOView, "object-view-sco")
router.register('objects/sros', arango_views.SROView, "object-view-sro")
router.register('objects/sdos', arango_views.SDOView, "object-view-sdo")
# txt2stix views
router.register('extractors', ExtractorsView, "extractors-view")

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
