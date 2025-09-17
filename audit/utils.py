"""
Utility functions for working with audit logs.
Provides a clean API for logging audit events from anywhere in the application.
"""
from django.contrib.auth import get_user_model
from django.db import models
from typing import Optional, Dict, Any, Union

from .models import AuditLog

User = get_user_model()


def log_event(
    action: str,
    user: Optional[User] = None,
    obj: Optional[models.Model] = None,
    request=None,
    metadata: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None,
    error_message: Optional[str] = None
) -> AuditLog:
    """
    Log an audit event.
    
    Args:
        action: The action that was performed (e.g., 'user_created', 'claim_updated')
        user: The user who performed the action (optional)
        obj: The object that was acted upon (optional)
        request: The HTTP request object (optional, used to get IP and user agent)
        metadata: Additional context about the event (optional)
        status_code: HTTP status code of the response (optional)
        error_message: Error message if the action failed (optional)
        
    Returns:
        The created AuditLog instance
    """
    # Prepare the metadata dictionary
    event_metadata = metadata or {}
    
    # Add error information if provided
    if error_message:
        event_metadata['error'] = error_message
    
    # Create the audit log entry
    log_entry = AuditLog(
        action=action,
        user=user if user and user.is_authenticated else None,
        status_code=status_code,
        error_message=error_message,
        metadata=event_metadata,
    )
    
    # Add request information if available
    if request:
        log_entry.ip_address = request.META.get('REMOTE_ADDR')
        log_entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]  # Truncate to max_length
    
    # Set up the generic relation if an object is provided
    if obj is not None:
        log_entry.content_object = obj
    
    # Save the log entry
    log_entry.save()
    
    return log_entry


def log_api_call(
    view_name: str,
    request,
    response=None,
    user: Optional[User] = None,
    obj: Optional[models.Model] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Log an API call as an audit event.
    
    Args:
        view_name: The name of the API view being called
        request: The HTTP request object
        response: The HTTP response object (optional)
        user: The user making the request (optional, defaults to request.user)
        obj: The object being acted upon (optional)
        metadata: Additional context about the API call (optional)
        
    Returns:
        The created AuditLog instance
    """
    # Get the user from the request if not provided
    if user is None and hasattr(request, 'user'):
        user = request.user
    
    # Prepare metadata
    api_metadata = {
        'view': view_name,
        'method': request.method,
        'path': request.path,
        'query_params': dict(request.query_params),
        **(metadata or {})
    }
    
    # Add response information if available
    if response is not None:
        api_metadata['status_code'] = response.status_code
    
    # Determine the action type based on the HTTP method
    method = request.method.lower()
    if method == 'get':
        action = 'api_read'
    elif method == 'post':
        action = 'api_create'
    elif method in ['put', 'patch']:
        action = 'api_update'
    elif method == 'delete':
        action = 'api_delete'
    else:
        action = f'api_{method}'
    
    # Log the event
    return log_event(
        action=action,
        user=user,
        obj=obj,
        request=request,
        metadata=api_metadata,
        status_code=getattr(response, 'status_code', None)
    )


def log_security_event(
    event_type: str,
    user: Optional[User] = None,
    request=None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Log a security-related event.
    
    Args:
        event_type: The type of security event (e.g., 'login_failed', 'password_reset')
        user: The user associated with the event (optional)
        request: The HTTP request object (optional)
        metadata: Additional context about the event (optional)
        
    Returns:
        The created AuditLog instance
    """
    return log_event(
        action=f'security_{event_type}',
        user=user,
        request=request,
        metadata=metadata or {}
    )


def get_audit_logs_for_object(
    obj: models.Model,
    action: Optional[str] = None,
    limit: int = 50
) -> models.QuerySet:
    """
    Get audit logs for a specific object.
    
    Args:
        obj: The object to get logs for
        action: Filter by a specific action (optional)
        limit: Maximum number of logs to return
        
    Returns:
        A QuerySet of AuditLog instances
    """
    from django.contrib.contenttypes.models import ContentType
    
    content_type = ContentType.objects.get_for_model(obj)
    queryset = AuditLog.objects.filter(
        content_type=content_type,
        object_id=str(obj.pk)
    ).order_by('-timestamp')
    
    if action:
        queryset = queryset.filter(action=action)
    
    return queryset[:limit]
