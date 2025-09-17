"""
Signal handlers for the audit app.
Automatically logs admin actions to the audit log.
"""
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.encoding import force_str

from .models import AuditLog

User = get_user_model()

# Map Django's action flags to our action types
ACTION_MAP = {
    ADDITION: 'created',
    CHANGE: 'updated',
    DELETION: 'deleted'
}

@receiver(post_save, sender=LogEntry)
def log_admin_action(sender, instance, created, **kwargs):
    """
    Log admin actions to the audit log.
    This captures all changes made through the Django admin interface.
    """
    # Skip if this is a test run or migration
    if hasattr(instance, '_no_audit_log') or getattr(instance, '_dirty', False):
        return
    
    try:
        # Get the user who performed the action
        user = instance.user if hasattr(instance, 'user') else None
        
        # Determine the action type
        action_flag = instance.action_flag
        action_type = ACTION_MAP.get(action_flag, 'other')
        
        # Format the action for our audit log
        model_name = instance.content_type.model
        action = f"{model_name}_{action_type}"
        
        # Prepare metadata
        metadata = {
            'admin_url': instance.get_admin_url(),
            'object_repr': str(instance.object_repr),
            'change_message': instance.change_message or '',
        }
        
        # For changes, include the changed fields if available
        if action_flag == CHANGE and hasattr(instance, 'get_changed_data'):
            metadata['changed_fields'] = instance.get_changed_data()
        
        # Create the audit log entry
        AuditLog.log_action(
            action=action,
            user=user,
            obj=instance.content_object,
            metadata=metadata
        )
        
    except Exception as e:
        # Log any errors but don't let them bubble up
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error logging admin action: {e}", exc_info=True)


def connect_signals():
    """
    Connect all signal handlers.
    This should be called from apps.py when the app is ready.
    """
    # The @receiver decorator already connects the signal,
    # but we keep this function for consistency and future use.
    pass
