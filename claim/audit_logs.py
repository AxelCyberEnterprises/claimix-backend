from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ClaimAuditLog(models.Model):
    """
    Model to track all changes to claims for audit purposes.
    """
    ACTION_CHOICES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('UPDATED', 'Claim Updated'),
        ('CREATED', 'Claim Created'),
        ('ESCALATED', 'Claim Escalated'),
        ('APPROVED', 'Claim Approved'),
        ('REJECTED', 'Claim Rejected'),
        ('COMMENT_ADDED', 'Comment Added'),
        ('FILE_ATTACHED', 'File Attached'),
    ]

    claim = models.ForeignKey('claim.Claim', on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, help_text="Stores additional context about the action")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Claim Audit Log'
        verbose_name_plural = 'Claim Audit Logs'

    def __str__(self):
        return f"{self.get_action_display()} - {self.claim.claim_id} - {self.timestamp}"
