from rest_framework import serializers
from claim.models.claim import Claim

class ClaimStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating a claim's status.
    """
    status = serializers.ChoiceField(
        choices=Claim.STATUS.choices,
        required=True,
        help_text="The new status for the claim"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional reason for the status change"
    )
    
    def validate_status(self, value):
        """
        Validate that the status is a valid choice.
        """
        if value not in dict(Claim.STATUS.choices):
            raise serializers.ValidationError("Invalid status value.")
        return value
