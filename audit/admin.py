from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import AuditLog


class ActionTypeFilter(admin.SimpleListFilter):
    """Filter audit logs by action type category."""
    title = _('action category')
    parameter_name = 'action_category'
    
    def lookups(self, request, model_admin):
        return [
            ('auth', _('Authentication')),
            ('user', _('User Management')),
            ('claim', _('Claims')),
            ('system', _('System')),
            ('api', _('API')),
            ('other', _('Other')),
        ]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value == 'auth':
            return queryset.filter(action__in=[
                'login', 'logout', 'login_failed', 'password_change', 'password_reset'
            ])
        elif value == 'user':
            return queryset.filter(action__in=[
                'user_created', 'user_updated', 'user_deleted', 'role_changed'
            ])
        elif value == 'claim':
            return queryset.filter(action__in=[
                'claim_created', 'claim_updated', 'claim_status_changed', 
                'claim_deleted', 'claim_file_uploaded', 'claim_file_deleted'
            ])
        elif value == 'system':
            return queryset.filter(action__in=[
                'settings_changed', 'maintenance_mode'
            ])
        elif value == 'api':
            return queryset.filter(action__in=[
                'api_call', 'api_error'
            ])
        elif value == 'other':
            return queryset.filter(action='other')
        return queryset


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model."""
    list_display = [
        'action_display', 'timestamp', 'user_display', 
        'object_display', 'status_code', 'ip_address'
    ]
    list_filter = [
        ActionTypeFilter, 'action', 'status_code', 'timestamp', 'user'
    ]
    search_fields = [
        'user__email', 'user__full_name', 'ip_address',
        'user_agent', 'metadata', 'error_message'
    ]
    readonly_fields = [
        'action_display', 'timestamp', 'user_display',
        'object_display', 'ip_address', 'user_agent',
        'status_code', 'error_message', 'metadata_display'
    ]
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    fieldsets = [
        (_('Action Details'), {
            'fields': [
                'action_display', 'timestamp', 'user_display',
                'object_display', 'status_code', 'ip_address',
                'user_agent', 'error_message', 'metadata_display'
            ]
        }),
    ]
    
    def action_display(self, obj):
        return obj.get_action_display()
    action_display.short_description = _('Action')
    
    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:authentication_customuser_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return _('System')
    user_display.short_description = _('User')
    user_display.admin_order_field = 'user__email'
    
    def object_display(self, obj):
        if obj.content_object:
            content_type = ContentType.objects.get_for_model(obj.content_object)
            admin_url = reverse(
                f'admin:{content_type.app_label}_{content_type.model}_change',
                args=[obj.object_id]
            )
            return format_html(
                '<a href="{}">{}: {}</a>', 
                admin_url, 
                content_type.model.capitalize(),
                str(obj.content_object)
            )
        return '—'
    object_display.short_description = _('Related Object')
    
    def metadata_display(self, obj):
        if not obj.metadata:
            return '—'
        
        items = []
        for key, value in obj.metadata.items():
            if isinstance(value, dict):
                value = ', '.join(f"{k}: {v}" for k, v in value.items())
            items.append(f"<strong>{key}:</strong> {value}")
        
        return format_html('<br>'.join(items))
    metadata_display.short_description = _('Metadata')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
