from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.fields import return_None

from policy_holder.models import Policy, PolicyHolder

User = get_user_model()

# Create your models here.
class Claim(models.Model):
    class CLAIM_TYPE(models.TextChoices):
        HEALTH = "Health","Health"
        PROPERTY = "Property", "Property"
        VEHICLE  = "Vehicle","Vehicle"
        BUSINESS = "Business", "Business"

    class TAGS(models.TextChoices):
        NEW = "New", "New"
        PROCESSING = "Processing", "Processing"
        WAITING_FOR_CUSTOMER_ACTION = "Waiting for customer action", "Waiting for customer action"
        AI_DECISION_READY = "AI decision ready", "AI decision ready"
        NEEDS_MANUAL_REVIEW= "Need manual review", "Need manual review"
        SENT_TO_MANAGER= "Sent to manager", "Sent to manager"
        AWAITING_PAYOUT = "Awaiting payout", "Awaiting payout"
        PAID= "Paid", "Paid"
        REJECTED= "Rejected", "Rejected"
        CLOSED= "Closed", "Closed"

    class STATUS(models.TextChoices):
        ACTIVE = "Active", "Active"
        RESOLVED = "Resolved", "Resolved"
        ESCALATED = "Escalated", "Escalated"

    claim_id = models.CharField(max_length=20, unique=True, editable=False, primary_key=True)
    sender_email = models.EmailField(max_length=255, null=True, blank=True, help_text="Email address of the claim submitter")
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, null=True, blank=True)
    policy_holder = models.ForeignKey(PolicyHolder, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=255,null=False, blank=False)
    claim_type = models.CharField(max_length=255, choices=CLAIM_TYPE.choices, null=True, blank=True) # AI
    urgency = models.CharField(max_length=255, null=True, blank=True) # AI
    tags = models.CharField(max_length=225, choices=TAGS.choices, default=TAGS.NEW, null=True, blank=True) # AI
    status = models.CharField(max_length=255, choices=STATUS.choices, default=STATUS.ACTIVE, null=True, blank=True) # AI
    incident_time = models.TimeField()
    incident_date = models.DateField()
    location_of_incident = models.TextField()
    description = models.TextField()
    images = models.ImageField(upload_to="claims/images/", null=True)
    document = models.FileField(upload_to="claims/documents/", null=True)
    claim_officer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    claim_notes = models.TextField(null=True, blank=True)
    next_action = models.TextField(null=True, blank=True)
    next_action_detail = models.TextField(null=True, blank=True)
    last_contacted = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.claim_id:
            prefix = "CLM"
            last_holder = Claim.objects.filter(claim_id__startswith=prefix).order_by('-claim_id').first()

            if last_holder:
                last_number = int(last_holder.claim_id.split('-')[-1])
                next_number = last_number + 1
            else:
                next_number = 1

            self.claim_id = f"{prefix}-{next_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Claim {self.claim_id}"



