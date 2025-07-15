from tkinter.font import names

from django.urls import path
from .api.views import ClaimListView,ClaimDetailView, ClaimUpdateView, ClaimDeleteView

urlpatterns = [
    path("", ClaimListView.as_view(), name="claim_list"),
    path("<str:pk>/detail/", ClaimDetailView.as_view(), name="claim_detail"),
    path("<str:pk>/update/", ClaimUpdateView.as_view(), name="claim_update"),
    path("<str:pk>/delete/", ClaimDeleteView.as_view(), name="claim_delete"),

]