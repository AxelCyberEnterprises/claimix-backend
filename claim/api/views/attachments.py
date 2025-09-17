from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from claim.models import Claim, ClaimAttachment
from authentication.permissions import IsAdmin, IsOwnerOrAdmin
from ..serializers.attachment import ClaimAttachmentSerializer, ClaimAttachmentListSerializer

class ClaimAttachmentView(APIView):
    """
    API endpoint for managing claim attachments.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self, claim_id):
        """
        Get the claim and verify the user has permission to access it.
        """
        claim = get_object_or_404(Claim, claim_id=claim_id)
        
        # Check if user is the owner or admin
        if not (self.request.user.is_staff or claim.claim_officer == self.request.user):
            self.permission_denied(
                self.request,
                message="You do not have permission to access these attachments"
            )
            
        return claim
    
    @swagger_auto_schema(
        operation_description="List all attachments for a claim",
        responses={
            200: ClaimAttachmentListSerializer(many=True),
            403: "Forbidden - No permission to access this claim's attachments",
            404: "Claim not found"
        },
        manual_parameters=[
            openapi.Parameter(
                'claim_id', 
                openapi.IN_PATH, 
                description="Claim ID", 
                type=openapi.TYPE_STRING
            ),
        ]
    )
    def get(self, request, claim_id):
        """
        List all attachments for a specific claim.
        """
        claim = self.get_queryset(claim_id)
        attachments = ClaimAttachment.objects.filter(claim=claim)
        serializer = ClaimAttachmentListSerializer(
            attachments, 
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Upload a new attachment for a claim",
        request_body=ClaimAttachmentSerializer,
        responses={
            201: ClaimAttachmentSerializer(),
            400: "Invalid input",
            403: "Forbidden - No permission to add attachments to this claim",
            404: "Claim not found"
        },
        manual_parameters=[
            openapi.Parameter(
                'claim_id', 
                openapi.IN_PATH, 
                description="Claim ID", 
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'file', 
                openapi.IN_FORM, 
                description="File to upload", 
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'description', 
                openapi.IN_FORM, 
                description="Optional description of the file", 
                type=openapi.TYPE_STRING,
                required=False
            ),
        ]
    )
    def post(self, request, claim_id):
        """
        Upload a new attachment for a specific claim.
        """
        claim = self.get_queryset(claim_id)
        
        # Add the claim to the serializer context
        context = {
            'request': request,
            'claim': claim
        }
        
        serializer = ClaimAttachmentSerializer(
            data=request.data,
            context=context
        )
        
        if serializer.is_valid():
            attachment = serializer.save()
            
            # Create an audit log entry for the attachment
            claim.audit_log(
                action='attachment_uploaded',
                user=request.user,
                details={
                    'attachment_id': str(attachment.id),
                    'filename': attachment.original_filename,
                    'file_type': attachment.file_type,
                    'description': attachment.description or ''
                },
                request=request
            )
            
            return Response(
                ClaimAttachmentSerializer(attachment, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='delete',
    operation_description="Delete a claim attachment",
    responses={
        204: "Attachment deleted successfully",
        403: "Forbidden - No permission to delete this attachment",
        404: "Attachment not found"
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsOwnerOrAdmin])
def delete_attachment(request, attachment_id):
    """
    Delete a specific attachment.
    Only the uploader or an admin can delete an attachment.
    """
    attachment = get_object_or_404(ClaimAttachment, id=attachment_id)
    
    # Check permissions
    if not (request.user.is_staff or attachment.uploaded_by == request.user):
        return Response(
            {"detail": "You do not have permission to delete this attachment"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Create audit log before deletion
    attachment.claim.audit_log(
        action='attachment_deleted',
        user=request.user,
        details={
            'attachment_id': str(attachment.id),
            'filename': attachment.original_filename,
            'file_type': attachment.file_type
        },
        request=request
    )
    
    # Delete the file and the database record
    attachment.file.delete(save=False)
    attachment.delete()
    
    return Response(status=status.HTTP_204_NO_CONTENT)
