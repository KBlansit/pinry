from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.urls import path, include

from core.views import drf_router, SiteSettingsView


admin.autodiscover()


urlpatterns = [
    # drf api
    path('api/v2/site-settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('api/v2/', include(drf_router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace="rest_framework")),

    # old api and views
    path('admin/', admin.site.urls),
    path('api/v2/profile/', include('users.urls')),
]


if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.IS_TEST:
    urlpatterns += staticfiles_urlpatterns()
