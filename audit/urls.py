from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'audit'

# Create a router for viewsets (if any)
router = DefaultRouter()

# API URL patterns
urlpatterns = [
    # List and filter audit logs
    path(
        'logs/',
        views.AuditLogListView.as_view(),
        name='audit-log-list'
    ),
    
    # Retrieve a specific audit log entry
    path(
        'logs/<uuid:pk>/',
        views.AuditLogDetailView.as_view(),
        name='audit-log-detail'
    ),
]

# Include router URLs if any
urlpatterns += router.urls
