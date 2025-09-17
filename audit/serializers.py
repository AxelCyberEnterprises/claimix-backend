from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import AuditLog


class ContentObjectRelatedField(serializers.RelatedField):
    """
    A custom field to handle generic foreign key relationships.
    Returns a serialized representation of the related object.
    """
    def to_representation(self, value):
        if not value:
            return None
            
        # Get the model name and ID
        model_name = value._meta.model_name
        app_label = value._meta.app_label
        model_pk = str(value.pk)
        
        # Create a basic representation with links
        return {
            'id': model_pk,
            'type': f"{app_label}.{model_name}",
            'display': str(value),
            'url': self.get_admin_url(value)
        }
    
    def get_admin_url(self, obj):
        """Generate admin URL for the object if possible"""
        try:
            content_type = ContentType.objects.get_for_model(obj)
            return reverse(
                'admin:%s_%s_change' % (content_type.app_label, content_type.model),
                args=[obj.pk]
            )
        except:
            return None


class UserSerializer(serializers.Serializer):
    """Basic user serializer for audit logs"""
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    
    def to_representation(self, instance):
        """Add admin URL to the user representation"""
        ret = super().to_representation(instance)
        if instance and hasattr(instance, 'id'):
            ret['url'] = reverse('admin:authentication_customuser_change', args=[instance.id])
        return ret


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AuditLog model.
    Provides a detailed view of audit log entries with related objects.
    """
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True,
        help_text=_('Human-readable action description')
    )
    
    user = UserSerializer(read_only=True)
    content_object = ContentObjectRelatedField(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'action_display',
            'timestamp',
            'user',
            'content_object',
            'ip_address',
            'status_code',
            'error_message',
            'metadata',
        ]
        read_only_fields = fields


class AuditLogListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing audit logs.
    Used for list views to improve performance.
    """
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True,
        help_text=_('Human-readable action description')
    )
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'action_display',
            'timestamp',
            'user_email',
            'user_name',
            'ip_address',
            'status_code',
        ]
        read_only_fields = fields
