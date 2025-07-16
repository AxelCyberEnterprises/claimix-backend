from rest_framework import serializers
from policy_holder.models import Policy,PolicyHolder

class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model =  Policy
        fields = "__all__"


class PolicyHolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyHolder
        fields= "__all__"