from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.db.models.signals import post_save

from authentication.models import CustomUser



@receiver(post_save, sender=CustomUser)
def assign_user_to_group(sender, instance, created, **kwargs):
    if created:
        if not hasattr(instance, "role"):
            raise ValueError("User does not have a role attribute")

        if instance.role == "Admin":
            group_name = "Admin"
        elif instance.role == "Claim Adjuster":
            group_name = "Claim Adjuster"
        elif instance.role == "Manager":
            group_name = "Manager"
        else:
            raise ValueError(
                f"Invalid role '{instance.role}' for user {instance.email}"
            )

        try:
            group = Group.objects.get(name=group_name)
        except ObjectDoesNotExist:
            raise ValueError(
                f"Group '{group_name}' does not exist. Please create it first."
            )

        instance.groups.add(group)


