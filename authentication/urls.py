from django.urls import path

from authentication.api.views import (
    AuthView, 
    LoginView, 
    LogoutView, 
    MeView, 
    StaffListView, 
    StaffDetailView,
    update_staff_role
)

urlpatterns = [
    path("register/", AuthView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("me/", MeView.as_view(), name="me"),
    path("staff/", StaffListView.as_view(), name="staff_list"),
    path("staff/<uuid:user_id>", StaffDetailView.as_view(), name="staff_detail"),
    path("staff/<uuid:user_id>/role", update_staff_role, name="update_staff_role"),
]
