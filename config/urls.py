from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "AirScan"
admin.site.site_title = "AirScan"
admin.site.index_title = "Monitor de passagens"

urlpatterns = [
    path("", include("voos.urls")),
    path("conta/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
]
