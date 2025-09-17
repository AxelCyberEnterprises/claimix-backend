from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import AuditLog
from .serializers import AuditLogListSerializer, AuditLogSerializer


class AuditLogListView(APIView):
    """
    API endpoint for retrieving system-wide audit logs.
    Only accessible by admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    # Define available filters for Swagger documentation
    filter_params = [
        openapi.Parameter(
            'action',
            openapi.IN_QUERY,
            description='Filter by action type',
            type=openapi.TYPE_STRING,
            enum=[action[0] for action in AuditLog.ActionType.choices]
        ),
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            description='Filter by user ID',
            type=openapi.TYPE_STRING,
            format='uuid'
        ),
        openapi.Parameter(
            'ip_address',
            openapi.IN_QUERY,
            description='Filter by IP address',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'status_code',
            openapi.IN_QUERY,
            description='Filter by HTTP status code',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter logs after this date (YYYY-MM-DD or ISO format)',
            type=openapi.TYPE_STRING,
            format='date'
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter logs before this date (YYYY-MM-DD or ISO format)',
            type=openapi.TYPE_STRING,
            format='date'
        ),
        openapi.Parameter(
            'object_type',
            openapi.IN_QUERY,
            description='Filter by object type (app_label.model_name)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'object_id',
            openapi.IN_QUERY,
            description='Filter by object ID',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search in user email, IP, user agent, or metadata',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'limit',
            openapi.IN_QUERY,
            description='Number of results per page (default: 50, max: 100)',
            type=openapi.TYPE_INTEGER,
            default=50
        ),
        openapi.Parameter(
            'offset',
            openapi.IN_QUERY,
            description='Initial index from which to return results',
            type=openapi.TYPE_INTEGER,
            default=0
        ),
    ]
    
    @swagger_auto_schema(
        operation_description="Retrieve system audit logs with filtering and pagination",
        manual_parameters=filter_params,
        responses={
            200: AuditLogListSerializer(many=True),
            400: "Invalid filter parameters",
            403: "Permission denied - admin access required"
        },
        tags=["Audit"]
    )
    def get(self, request):
        """
        List all audit log entries with optional filtering.
        """
        try:
            queryset = AuditLog.objects.all()
            queryset = self.apply_filters(queryset, request)
            
            # Get pagination parameters
            limit = min(int(request.query_params.get('limit', 50)), 100)
            offset = int(request.query_params.get('offset', 0))
            
            # Get total count before pagination
            total_count = queryset.count()
            
            # Apply pagination
            queryset = queryset.order_by('-timestamp')[offset:offset + limit]
            
            # Serialize the data
            serializer = AuditLogListSerializer(
                queryset,
                many=True,
                context={'request': request}
            )
            
            # Prepare response with pagination metadata
            response_data = {
                'count': total_count,
                'next': self._get_next_page_url(request, offset, limit, total_count),
                'previous': self._get_previous_page_url(request, offset, limit),
                'results': serializer.data
            }
            
            return Response(response_data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def apply_filters(self, queryset, request):
        """Apply filters to the queryset based on request parameters."""
        params = request.query_params
        
        # Filter by action type
        if 'action' in params:
            queryset = queryset.filter(action=params['action'])
            
        # Filter by user
        if 'user_id' in params:
            queryset = queryset.filter(user_id=params['user_id'])
            
        # Filter by IP address
        if 'ip_address' in params:
            queryset = queryset.filter(ip_address=params['ip_address'])
            
        # Filter by status code
        if 'status_code' in params:
            queryset = queryset.filter(status_code=params['status_code'])
            
        # Filter by date range
        if 'date_from' in params:
            try:
                date_from = self._parse_date(params['date_from'])
                queryset = queryset.filter(timestamp__gte=date_from)
            except ValueError as e:
                raise ValueError("Invalid date_from format. Use YYYY-MM-DD or ISO format.")
                
        if 'date_to' in params:
            try:
                date_to = self._parse_date(params['date_to']) + timedelta(days=1)
                queryset = queryset.filter(timestamp__lt=date_to)
            except ValueError as e:
                raise ValueError("Invalid date_to format. Use YYYY-MM-DD or ISO format.")
        
        # Filter by object type and ID
        if 'object_type' in params:
            try:
                app_label, model_name = params['object_type'].split('.')
                content_type = ContentType.objects.get(
                    app_label=app_label,
                    model=model_name.lower()
                )
                queryset = queryset.filter(content_type=content_type)
                
                if 'object_id' in params:
                    queryset = queryset.filter(object_id=params['object_id'])
                    
            except (ValueError, ContentType.DoesNotExist):
                raise ValueError("Invalid object_type format. Use 'app_label.model_name'.")
        
        # Search across multiple fields
        if 'search' in params:
            search_term = params['search']
            queryset = queryset.filter(
                Q(user__email__icontains=search_term) |
                Q(ip_address__icontains=search_term) |
                Q(user_agent__icontains=search_term) |
                Q(metadata__icontains=search_term) |
                Q(error_message__icontains=search_term)
            )
        
        return queryset
    
    def _parse_date(self, date_str):
        """Parse date string in either YYYY-MM-DD or ISO format."""
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try YYYY-MM-DD format
                return datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format")
    
    def _get_next_page_url(self, request, offset, limit, total_count):
        """Generate URL for the next page of results."""
        if offset + limit >= total_count:
            return None
        
        params = request.query_params.copy()
        params['offset'] = offset + limit
        return f"{request.path}?{params.urlencode()}"
    
    def _get_previous_page_url(self, request, offset, limit):
        """Generate URL for the previous page of results."""
        if offset <= 0:
            return None
        
        params = request.query_params.copy()
        params['offset'] = max(0, offset - limit)
        return f"{request.path}?{params.urlencode()}"


class AuditLogDetailView(APIView):
    """
    API endpoint for retrieving a single audit log entry.
    Only accessible by admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @swagger_auto_schema(
        operation_description="Retrieve a specific audit log entry by ID",
        responses={
            200: AuditLogSerializer(),
            403: "Permission denied - admin access required",
            404: "Audit log entry not found"
        },
        tags=["Audit"]
    )
    def get(self, request, pk):
        """Retrieve a specific audit log entry."""
        try:
            log_entry = AuditLog.objects.get(pk=pk)
            serializer = AuditLogSerializer(
                log_entry,
                context={'request': request}
            )
            return Response(serializer.data)
            
        except AuditLog.DoesNotExist:
            return Response(
                {'error': 'Audit log entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
