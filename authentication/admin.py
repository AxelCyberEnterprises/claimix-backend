from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    list_display = [
        "email",
        "role",
        "is_active",
        "is_staff",
        "is_superuser"
    ]
    list_filter = ("is_active", "is_staff")

    fieldsets = [
        (
            None,
            {
                "fields": ["full_name", "email", "role"],
            },
        ),

        (
            "Permissions",
            {
                "fields": [
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ]
            },
        ),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "full_name",
                    "email",
                    "role",
                    "password1",
                    "password2"
                ],
            },
        )
    ]
    search_fields = ["email"]
    ordering = ["email"]
    filter_horizontal = ["groups", "user_permissions"]


admin.site.register(CustomUser, CustomUserAdmin)
