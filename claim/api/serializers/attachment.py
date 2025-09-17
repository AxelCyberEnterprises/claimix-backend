from rest_framework import serializers
from claim.models import ClaimAttachment
from django.core.validators import FileExtensionValidator

class ClaimAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the ClaimAttachment model.
    Handles file uploads and metadata for claim attachments.
    """
    file = serializers.FileField(
        required=True,
        allow_null=False,
        write_only=True,
        help_text="The file to be uploaded. Max size is 10MB."
    )
    
    file_url = serializers.SerializerMethodField(
        read_only=True,
        help_text="URL to access the uploaded file"
    )
    
    file_type_display = serializers.CharField(
        source='get_file_type_display',
        read_only=True,
        help_text="Human-readable file type"
    )
    
    file_size = serializers.SerializerMethodField(
        help_text="Human-readable file size"
    )
    
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name',
        read_only=True,
        help_text="Name of the user who uploaded the file"
    )
    
    class Meta:
        model = ClaimAttachment
        fields = [
            'id',
            'file',
            'file_url',
            'original_filename',
            'file_type',
            'file_type_display',
            'file_size',
            'description',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'file_url',
            'original_filename',
            'file_type',
            'file_type_display',
            'file_size',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
            'updated_at',
        ]
    
    def get_file_url(self, obj):
        """
        Get the absolute URL for the file.
        """
        if obj.file and hasattr(obj.file, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size(self, obj):
        """
        Return human-readable file size.
        """
        return obj.file_size
    
    def validate_file(self, value):
        """
        Validate the uploaded file.
        """
        # File size validation is handled by the model's clean method
        # and the file field's validators
        return value
    
    def create(self, validated_data):
        """
        Create a new attachment and associate it with the claim and user.
        """
        # Get the claim from the view's context
        claim = self.context.get('claim')
        if not claim:
            raise serializers.ValidationError("Claim not found in context")
        
        # Set the claim and uploaded_by fields
        validated_data['claim'] = claim
        validated_data['uploaded_by'] = self.context['request'].user
        
        # The original filename will be set in the model's save() method
        return super().create(validated_data)


class ClaimAttachmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing attachments without file data.
    """
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name')
    
    class Meta:
        model = ClaimAttachment
        fields = [
            'id',
            'file_url',
            'original_filename',
            'file_type',
            'file_size',
            'description',
            'uploaded_by_name',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_file_url(self, obj):
        if obj.file and hasattr(obj.file, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size(self, obj):
        return obj.file_size
