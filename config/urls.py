from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/transfers/", include("transfers.urls")),
    path("api/reviews/", include("reviews.urls")),
]
