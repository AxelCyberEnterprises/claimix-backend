from django.urls import path

from policy_holder.api.views import PolicyView,PolicyDetailView, PolicyHolderView, PolicyHolderDetailView

urlpatterns = [
    path("policy/", PolicyView.as_view(), name="get_policies"),
    path("policy/<str:pk>/",PolicyDetailView.as_view(), name="get_policy"),
    path("policyholder/", PolicyHolderView.as_view(), name="get_policies_holders"),
    path("policyholder/<str:pk>/", PolicyHolderDetailView.as_view(), name="get_policies_holder"),
]