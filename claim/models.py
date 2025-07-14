from django.db import models
from policy_holder.models import Policy, PolicyHolder

# Create your models here.
class Claim(models.Model):
    class CLAIM_TYPE(models.TextChoices):
        HEALTH = "Health","Health"
        PROPERTY = "Property", "Property"
        VEHICLE  = "Vehicle","Vehicle"
        BUSINESS = "Business", "Business"

    class TAGS(models.TextChoices):
        NONE = "None", "None"
        FRAUD_PREVIEW = "Fraud Preview", "Fraud Preview"
        ESCALATED = "Escalated", "Escalated"
        URGENT = "URGENT", "URGENT"

    claim_id = models.CharField(max_length=20, unique=True, editable=False, primary_key=True)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, null=False, blank=False)
    policy_holder = models.ForeignKey(PolicyHolder, on_delete=models.CASCADE, null=False, blank=False)
    full_name = models.CharField(max_length=255,null=False, blank=False)
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPE.choices)
    tags = models.CharField(max_length=20, choices=TAGS.choices)
    incident_time = models.TimeField()
    incident_date = models.DateField()
    location_of_incident = models.TextField()
    description = models.TextField()
    images = models.ImageField(upload_to="claims/images/", null=True)
    document = models.FileField(upload_to="claims/documents/", null=True)
    created_at = models.DateTimeField(auto_now_add=True)

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