from django.urls import path
from .api.views import ClaimListView,ClaimDetailView

urlpatterns = [
    path("", ClaimListView.as_view(), name="claim_list"),
    path("detail/<str:pk>/",ClaimDetailView.as_view(), name="claim_detail")
]