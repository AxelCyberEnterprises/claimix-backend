from rest_framework import  serializers
from claim.models import Claim


class ClaimSerializer(serializers.ModelSerializer):
    incident_time = serializers.TimeField(input_formats=[
        '%I:%M %p'  # e.g., 9:30 AM
    ])
    incident_date = serializers.DateField(input_formats=['%Y-%m-%d']) # e.g 2024-07-14
    class Meta:
        model = Claim
        fields = '__all__'
        read_only_fields = ['claim_id', "created_at"]


class ClaimDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = '__all__'