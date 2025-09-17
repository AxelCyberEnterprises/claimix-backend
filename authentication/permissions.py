from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsInGroup(BasePermission):
    group_name = None

    def has_permission(self, request, view):
        return (
                request.user.is_authenticated
                and request.user.groups.filter(name=self.group_name).exists()
        )

class IsAdmin(IsInGroup):
    group_name = "Admin"


class IsManager(IsInGroup):
    group_name = "Manager"


class IsClaimAdjuster(IsInGroup):
    group_name = "Claim Adjuster"


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission to only allow owners of an object or admins to edit it.
    Assumes the model instance has an `owner` attribute.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in SAFE_METHODS:
            return True
            
        # Instance must have an attribute named `owner` or `claim_officer`
        if hasattr(obj, 'owner'):
            return obj.owner == request.user or request.user.is_staff
        elif hasattr(obj, 'claim_officer'):
            return obj.claim_officer == request.user or request.user.is_staff
            
        # Default to False if we can't determine ownership
        return False
