from django.urls import path

from authentication.api.views import AuthView

urlpatterns = [
    path("register/", AuthView.as_view(), name="register")
]
