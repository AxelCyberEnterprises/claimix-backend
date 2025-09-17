from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from authentication.models import CustomUser
from authentication.permissions import IsAdmin

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    Provides a basic representation of user data.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role']
        read_only_fields = ['id', 'email', 'full_name', 'role']



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


class StaffRoleUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating staff roles.
    Only admins can update roles, and they cannot modify their own role.
    """
    class Meta:
        model = CustomUser
        fields = ["role", "status", "department"]
        read_only_fields = ["email", "full_name"]
    
    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            raise ValidationError("Request context is required")
        
        # Get the target user (the one being updated)
        target_user = self.instance
        requesting_user = request.user
        
        # Check if the requesting user is an admin
        if not (requesting_user.is_staff or requesting_user.role == "Admin"):
            raise PermissionDenied("Only administrators can update staff roles")
        
        # Prevent users from modifying their own role
        if target_user == requesting_user:
            raise ValidationError("You cannot modify your own role")
        
        # Validate role transitions (add any business rules here)
        new_role = attrs.get('role')
        if new_role:
            valid_roles = [role[0] for role in CustomUser.ROLE.choices]
            if new_role not in valid_roles:
                raise ValidationError({"role": f"Invalid role. Must be one of: {', '.join(valid_roles)}"})
            
            # Prevent demoting the last admin
            if (target_user.role == "Admin" and 
                new_role != "Admin" and
                CustomUser.objects.filter(role="Admin").count() <= 1):
                raise ValidationError("Cannot demote the last administrator")
        
        # Validate status if being updated
        new_status = attrs.get('status')
        if new_status:
            valid_statuses = [status[0] for status in CustomUser.STATUS.choices]
            if new_status not in valid_statuses:
                raise ValidationError({"status": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"})
        
        # Validate department if being updated
        new_department = attrs.get('department')
        if new_department:
            valid_departments = [dept[0] for dept in CustomUser.DEPARTMENT.choices]
            if new_department not in valid_departments:
                raise ValidationError({"department": f"Invalid department. Must be one of: {', '.join(valid_departments)}"})
        
        return attrs
    
    def update(self, instance, validated_data):
        # Log the role change (you can implement audit logging here)
        old_role = instance.role
        old_status = instance.status
        old_department = instance.department
        
        # Update the instance
        instance = super().update(instance, validated_data)
        
        # Create an audit log entry
        changes = []
        if 'role' in validated_data and validated_data['role'] != old_role:
            changes.append(f"Role changed from {old_role} to {validated_data['role']}")
        if 'status' in validated_data and validated_data['status'] != old_status:
            changes.append(f"Status changed from {old_status} to {validated_data['status']}")
        if 'department' in validated_data and validated_data['department'] != old_department:
            changes.append(f"Department changed from {old_department} to {validated_data['department']}")
        
        # TODO: Add audit logging here
        # Example: create_audit_log(
        #     user=request.user,
        #     action='staff_role_updated',
        #     target_user=instance,
        #     changes=', '.join(changes) if changes else 'No changes',
        #     request=request
        # )
        
        return instance
