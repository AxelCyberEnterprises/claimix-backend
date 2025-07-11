import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager, PermissionsMixin
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email=None, password=None, role=None, **extra_fields):
        if not email:
            raise ValueError("A user must provide an email")
        user = self.model(
            email=self.normalize_email(email),
            role=role,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.is_active = True

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, role, **extra_fields):
        user = self.create_user(email, password, role='Admin', **extra_fields)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class ROLE(models.TextChoices):
        CLAIM_ADJUSTER = "Claim Adjuster", "Claim Adjuster"
        ADMIN = "Admin", "Admin"
        MANAGER = "Manager", "Manager"

    user_id = models.UUIDField(
        primary_key=True, unique=True, default=uuid.uuid4, editable=False
    )
    email = models.EmailField(null=False, blank=False, unique=True)
    role = models.CharField(max_length=20, choices=ROLE.choices, default=ROLE.CLAIM_ADJUSTER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    object = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["role"]

    @property
    def is_manager(self):
        # is the user a manager
        return self.role == 'Manager'

    @property
    def is_claim_adjuster(self):
        # is the user a claim adjuster
        return self.role == 'Claim Adjuster'

    def __str__(self):
        return self.email
