from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.shortcuts import get_object_or_404

from claim.models import Claim, ClaimAuditLog
from authentication.permissions import IsOwnerOrAdmin, IsAdmin
from ..serializers.audit_log import ClaimAuditLogSerializer

class ClaimAuditLogView(APIView):
    """
    API endpoint for retrieving the audit trail of a claim.
    """
    permission_classes = [IsAuthenticated, (IsOwnerOrAdmin | IsAdmin)]
    
    @swagger_auto_schema(
        operation_description="Retrieve the audit trail for a specific claim",
        responses={
            200: ClaimAuditLogSerializer(many=True),
            403: "Forbidden - No permission to view this claim's audit trail",
            404: "Claim not found"
        },
        manual_parameters=[
            openapi.Parameter(
                'claim_id', 
                openapi.IN_PATH, 
                description="Claim ID", 
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'action', 
                openapi.IN_QUERY, 
                description="Filter by action type (e.g., 'STATUS_CHANGE', 'FILE_ATTACHED')", 
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'user_id', 
                openapi.IN_QUERY, 
                description="Filter by user ID who performed the action", 
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'start_date', 
                openapi.IN_QUERY, 
                description="Filter by start date (YYYY-MM-DD)", 
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'end_date', 
                openapi.IN_QUERY, 
                description="Filter by end date (YYYY-MM-DD)", 
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'limit', 
                openapi.IN_QUERY, 
                description="Maximum number of results to return (default: 50, max: 100)", 
                type=openapi.TYPE_INTEGER,
                default=50
            ),
            openapi.Parameter(
                'offset', 
                openapi.IN_QUERY, 
                description="Number of results to skip for pagination", 
                type=openapi.TYPE_INTEGER,
                default=0
            ),
        ]
    )
    def get(self, request, claim_id):
        """
        Retrieve the audit trail for a specific claim with optional filtering.
        """
        # Get the claim and check permissions
        claim = get_object_or_404(Claim, claim_id=claim_id)
        
        # Check if user has permission to view this claim's audit trail
        if not (request.user.is_staff or claim.claim_officer == request.user):
            return Response(
                {"detail": "You do not have permission to view this claim's audit trail"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Start with base queryset
        queryset = ClaimAuditLog.objects.filter(claim=claim)
        
        # Apply filters
        action = request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
        
        # Apply pagination
        limit = min(int(request.query_params.get('limit', 50)), 100)  # Max 100 results
        offset = int(request.query_params.get('offset', 0))
        
        # Get total count before pagination
        total_count = queryset.count()
        
        # Apply pagination
        queryset = queryset.order_by('-timestamp')[offset:offset + limit]
        
        # Serialize the data
        serializer = ClaimAuditLogSerializer(
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
