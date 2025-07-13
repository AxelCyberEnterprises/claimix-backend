from django.db import models
from django.utils import timezone

# Create your models here.
class Policy(models.Model):
    policy_id = models.CharField(max_length=20, unique=True, editable=False, primary_key=True)
    coverage = models.TextField()
    premium = models.DecimalField(max_digits=10,decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.policy_id:
            current_year = timezone.now().year
            prefix = f"POL-{current_year}"

            # Get latest policy with same year prefix
            last_policy = Policy.objects.filter(policy_id__startswith=prefix).order_by('-id').first()

            if last_policy:
                # Extract last number after the last dash (e.g. POL-2024-3 -> 3)
                last_number = int(last_policy.policy_id.split("-")[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.policy_id = f"{prefix}-{next_number}"

        super().save(*args, **kwargs)

    class Meta:
        verbose_name=("Policy")
        verbose_name_plural = ("Policies")
        ordering = ["policy_id"]

    def __str__(self):
        return self.policy_id

class PolicyHolder(models.Model):
    policy_holder_id = models.CharField(max_length=20, unique=True, editable=False, primary_key=True)
    full_name = models.CharField(max_length=255)
    email  = models.EmailField()
    seniority = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        if not self.policy_holder_id:
            prefix = "CUST"
            last_holder = PolicyHolder.objects.filter(policy_holder_id__startswith=prefix).order_by('-policy_holder_id').first()

            if last_holder:
                last_number = int(last_holder.policy_holder_id.split('-')[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.policy_holder_id = f"{prefix}-{next_number}"

        super().save(*args, **kwargs)

    class Meta:
        verbose_name=("PolicyHolder")
        verbose_name_plural = ("PoliciesHolders")
        ordering = ["policy_holder_id"]

    def __str__(self):
        return self.policy_holder_id


class PolicySubscription(models.Model):
    class STATUS(models.TextChoices):
        ACTIVE = "Active", "Active"
        LAPSED = "Lapsed", "Lapsed"
        BLACKLISTED = "Blacklisted", "Blacklisted"
    policy_holder = models.ForeignKey(PolicyHolder,on_delete=models.CASCADE, null=False, blank=False)
    policy = models.ForeignKey(Policy,on_delete=models.CASCADE, null=False, blank=False)
    total_claims = models.PositiveIntegerField()
    start_date = models.DateField()
    last_renewal_date = models.DateField()
    next_renewal_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS.choices, default=STATUS.ACTIVE)

    class Meta:
        verbose_name=("PolicySubscription")
        verbose_name_plural = ("PoliciesSubscription")
        ordering = ["policy_holder"]

    def __str__(self):
        return f'Policy {self.policy} held by {self.policy_holder}'