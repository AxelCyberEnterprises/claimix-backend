"""
Middleware for automatic audit logging of API requests.
"""
import time
from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .utils import log_api_call


class AuditMiddleware:
    """
    Middleware that logs all API requests to the audit log.
    
    This middleware logs:
    - All API requests and responses
    - Request method, path, and query parameters
    - Response status code
    - Processing time
    - User information (if authenticated)
    """
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip logging for certain paths (e.g., admin, static files)
        if self._should_skip_logging(request):
            return self.get_response(request)
        
        # Get the start time for calculating processing time
        start_time = time.time()
        
        # Process the request and get the response
        response = self.get_response(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        try:
            # Log the API call
            self._log_api_call(request, response, process_time)
        except Exception as e:
            # Don't let logging errors break the request/response cycle
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error logging API call: {e}", exc_info=True)
        
        return response
    
    def _should_skip_logging(self, request: HttpRequest) -> bool:
        """Determine if the request should be skipped for logging."""
        # Skip admin and static/media files
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/healthz',
            '/readiness',
            '/metrics',
        ]
        
        return any(request.path.startswith(path) for path in skip_paths)
    
    def _log_api_call(self, request: HttpRequest, response: HttpResponse, process_time: float):
        """Log the API call to the audit log."""
        # Get the view name if available
        view_name = self._get_view_name(request)
        
        # Prepare metadata
        metadata = {
            'process_time_seconds': round(process_time, 4),
            'request_method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'response_status': response.status_code,
            'response_content_type': response.get('Content-Type', '').split(';')[0],
        }
        
        # Add request body for non-GET requests (with size limit)
        if request.method != 'GET' and hasattr(request, 'body'):
            max_body_size = 1000  # Maximum size of request body to log
            body = str(request.body)
            if len(body) > max_body_size:
                body = body[:max_body_size] + '... (truncated)'
            metadata['request_body'] = body
        
        # Log the API call
        log_api_call(
            view_name=view_name,
            request=request,
            response=response,
            metadata=metadata
        )
    
    def _get_view_name(self, request: HttpRequest) -> str:
        """Get the name of the view handling the request."""
        if hasattr(request, 'resolver_match') and request.resolver_match:
            # Try to get the view name from the resolver match
            view_name = (
                request.resolver_match.view_name or
                request.resolver_match.url_name or
                request.resolver_match.func.__name__
            )
            return str(view_name)
        
        # Fall back to the path if we can't determine the view name
        return request.path
