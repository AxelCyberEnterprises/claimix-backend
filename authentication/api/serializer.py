from django.contrib.auth import get_user_model
from rest_framework import serializers

from authentication.models import CustomUser

User = get_user_model()


class AuthSerializer(serializers.ModelSerializer):
    ROLE_CHOICES = [
        ["Claim Adjuster", "Claim Adjuster"],
        ["Admin", "Admin"],
        ["Manager", "Manager"],
    ]
    role = serializers.CharField()

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "role",
            "password"
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_role(self, value):
        # Normalize to title case
        normalized_value = value.strip().title()

        valid_roles = [choice[0] for choice in self.ROLE_CHOICES]

        if normalized_value not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        return normalized_value

    def create(self, validated_data):
        user = User.object.create(**validated_data)
        return user
