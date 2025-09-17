from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

class AuditLog(models.Model):
    """
    System-wide audit log for tracking user actions across the application.
    """
    class ActionType(models.TextChoices):
        # Authentication actions
        LOGIN = 'login', _('User Login')
        LOGOUT = 'logout', _('User Logout')
        LOGIN_FAILED = 'login_failed', _('Failed Login Attempt')
        PASSWORD_CHANGE = 'password_change', _('Password Changed')
        PASSWORD_RESET = 'password_reset', _('Password Reset')
        
        # User management actions
        USER_CREATED = 'user_created', _('User Created')
        USER_UPDATED = 'user_updated', _('User Updated')
        USER_DELETED = 'user_deleted', _('User Deleted')
        ROLE_CHANGED = 'role_changed', _('User Role Changed')
        
        # Claim actions
        CLAIM_CREATED = 'claim_created', _('Claim Created')
        CLAIM_UPDATED = 'claim_updated', _('Claim Updated')
        CLAIM_STATUS_CHANGED = 'claim_status_changed', _('Claim Status Changed')
        CLAIM_DELETED = 'claim_deleted', _('Claim Deleted')
        CLAIM_FILE_UPLOADED = 'claim_file_uploaded', _('Claim File Uploaded')
        CLAIM_FILE_DELETED = 'claim_file_deleted', _('Claim File Deleted')
        
        # System actions
        SETTINGS_CHANGED = 'settings_changed', _('System Settings Changed')
        MAINTENANCE_MODE = 'maintenance_mode', _('Maintenance Mode Toggled')
        
        # API actions
        API_CALL = 'api_call', _('API Call')
        API_ERROR = 'api_error', _('API Error')
        
        # Other
        OTHER = 'other', _('Other')
    
    # Core fields
    action = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        help_text=_('The type of action that was performed')
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_('When the action occurred')
    )
    
    # User who performed the action
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        help_text=_('The user who performed the action (if authenticated)')
    )
    
    # Generic foreign key to the object this log entry is about
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_('The type of the related object')
    )
    object_id = models.UUIDField(
        null=True,
        blank=True,
        help_text=_('The ID of the related object')
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Request/response details
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_('IP address of the client')
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text=_('User agent of the client')
    )
    
    # Additional context
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional context about the action')
    )
    
    # Status and error information
    status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=_('HTTP status code of the response')
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text=_('Error message if the action failed')
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.timestamp}"
    
    @classmethod
    def log_action(cls, action, user=None, request=None, obj=None, **metadata):
        """
        Helper method to create a new audit log entry.
        
        Args:
            action (str): The action type (from ActionType)
            user (User, optional): The user who performed the action
            request (HttpRequest, optional): The request object
            obj (Model, optional): The object this action is about
            **metadata: Additional context to store in the metadata field
            
        Returns:
            AuditLog: The created audit log entry
        """
        log_entry = cls(
            action=action,
            user=user if user and user.is_authenticated else None,
            **metadata
        )
        
        if request:
            log_entry.ip_address = request.META.get('REMOTE_ADDR')
            log_entry.user_agent = request.META.get('HTTP_USER_AGENT')
            
            # Get status code from response if available
            if hasattr(request, 'response'):
                log_entry.status_code = request.response.status_code
        
        # Set up generic relation if an object is provided
        if obj is not None:
            log_entry.content_object = obj
        
        log_entry.save()
        return log_entry
