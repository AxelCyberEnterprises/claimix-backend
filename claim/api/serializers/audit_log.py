from rest_framework import serializers
from claim.models import ClaimAuditLog
from authentication.models import CustomUser


class AuditUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for user information in audit logs.
    Only includes essential identifying information.
    """
    class Meta:
        model = CustomUser
        fields = ['user_id', 'email', 'full_name']
        read_only_fields = fields

class ClaimAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for ClaimAuditLog model.
    Provides a detailed view of audit log entries.
    """
    user = AuditUserSerializer(read_only=True)
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True,
        help_text="Human-readable action description"
    )
    
    class Meta:
        model = ClaimAuditLog
        fields = [
            'id',
            'action',
            'action_display',
            'user',
            'timestamp',
            'details',
            'ip_address',
        ]
        read_only_fields = fields
    
    def to_representation(self, instance):
        """
        Customize the representation of the audit log entry.
        """
        representation = super().to_representation(instance)
        
        # Format the timestamp in a more readable format
        representation['timestamp'] = instance.timestamp.isoformat()
        
        # Add additional context based on action type
        if instance.action == 'STATUS_CHANGE':
            representation['old_status'] = instance.details.get('old_status')
            representation['new_status'] = instance.details.get('new_status')
            representation['reason'] = instance.details.get('reason', '')
        elif instance.action in ['FILE_ATTACHED', 'FILE_DELETED']:
            representation['filename'] = instance.details.get('filename')
            representation['file_type'] = instance.details.get('file_type')
        
        return representation
