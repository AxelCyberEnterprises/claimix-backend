from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create default group and permission"

    def handle(self, *args, **options):
        groups = {
            "Admin": [],
            "Manager": [],
            "Claim Adjuster": [],
        }

        for group_name, permissions in groups.items():
            # Create or get the group
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f"Group created:{group_name} created.")
            for model, perms in permissions:
                content_type = ContentType.objects.get_for_model(model)
                for perm in perms:
                    codename = f"{perm}_{model._meta.model_name}"
                    permission, _ = Permission.objects.get_or_create(
                        codename=codename,
                        content_type=content_type,
                        defaults={"name": f"can {perm} {model._meta.verbose_name}"},
                    )
                    group.permissions.add(permission)
                    self.stdout.write(
                        f"Permission '{codename}' added to group '{group_name}'."
                    )

        self.stdout.write(
            self.style.SUCCESS("Default groups and permissions intialized")
        )
