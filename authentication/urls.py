from django.urls import path

from authentication.api.views import AuthView,LoginView,LogoutView


urlpatterns = [
    path("register/", AuthView.as_view(), name="register"),
    path("login/",LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name='logout'),
]
