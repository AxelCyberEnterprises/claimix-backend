from django.contrib import admin
from .models.claim import Claim
from .models.audit_logs import ClaimAuditLog

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_id', 'full_name', 'status', 'claim_type', 'created_at')
    list_filter = ('status', 'claim_type', 'tags')
    search_fields = ('claim_id', 'full_name', 'policy_holder__full_name')
    readonly_fields = ('claim_id', 'created_at', 'updated_at')

@admin.register(ClaimAuditLog)
class ClaimAuditLogAdmin(admin.ModelAdmin):
    list_display = ('claim', 'action', 'user', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('claim__claim_id', 'user__email', 'details')
    readonly_fields = ('timestamp', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'
