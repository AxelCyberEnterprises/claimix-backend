from rest_framework.permissions import  BasePermission

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


