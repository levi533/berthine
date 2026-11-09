from django.urls import path

from . import views

urlpatterns = [
    path("currencies/", views.currencies, name="currencies"),
    path("quote/", views.create_quote, name="quote"),
    path("", views.create_transfer, name="create-transfer"),
    path("history/", views.transfer_history, name="transfer-history"),
]
