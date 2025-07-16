from django.contrib.auth import get_user_model, authenticate
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
        password = validated_data.pop("password")
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        attrs["user"] = user
        return attrs


class StaffSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)
    last_login = serializers.DateTimeField(format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = CustomUser
        fields = ["user_id","full_name", "email", "role","department", "status","created_at","last_login"]
        read_only_fields = ["user_id","created_at","last_login"]


class StaffAuditSerializer(StaffSerializer):
    audit_logs = serializers.SerializerMethodField()

    class Meta(StaffSerializer.Meta):
        fields = StaffSerializer.Meta.fields + ['audit_logs']

    def get_audit_logs(self, obj):
        # Replace this with your actual audit retrieval logic
        return [
            {
                "name": "Audit 1",

            },
            {
                "name": "Audit 2",

            }
        ]

