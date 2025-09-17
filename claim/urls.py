from django.urls import path
from claim.api.views.views import (
    ClaimListView, 
    ClaimDetailView, 
    ClaimUpdateView, 
    ClaimDeleteView,
    update_claim_status,
    ClaimViewSet
)
from claim.api.views.attachments import ClaimAttachmentView, delete_attachment
from claim.api.views.audit import ClaimAuditLogView

urlpatterns = [
    # Claim management endpoints
    path("", ClaimListView.as_view(), name="claim_list"),
    path("<str:claim_id>/detail/", ClaimDetailView.as_view(), name="claim_detail"),
    path("<str:pk>/update/", ClaimUpdateView.as_view(), name="claim_update"),
    path("<str:pk>/delete/", ClaimDeleteView.as_view(), name="claim_delete"),
    path("<str:claim_id>/status/", update_claim_status, name="claim_status_update"),
    
    # Attachment endpoints
    path(
        "<str:claim_id>/attachments/", 
        ClaimAttachmentView.as_view(), 
        name="claim_attachments"
    ),
    path(
        "attachments/<uuid:attachment_id>/delete/", 
        delete_attachment, 
        name="delete_attachment"
    ),
    
    # Audit log endpoint
    path(
        "<str:claim_id>/audit/", 
        ClaimAuditLogView.as_view(), 
        name="claim_audit_logs"
    ),
]