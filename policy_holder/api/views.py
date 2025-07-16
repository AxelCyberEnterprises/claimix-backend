from rest_framework import generics
from django.db.models.functions import Substr, Cast
from django.db.models import IntegerField

from policy_holder.models import Policy,PolicyHolder
from policy_holder.api.serializer import PolicySerializer, PolicyHolderSerializer

class PolicyView(generics.ListAPIView):
    serializer_class = PolicySerializer

    def get_queryset(self):
        return Policy.objects.annotate(
            num_part=Cast(Substr('policy_id', 10), IntegerField())
        ).order_by('num_part')

class PolicyDetailView(generics.RetrieveAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer

class PolicyHolderView(generics.ListAPIView):
    serializer_class = PolicyHolderSerializer

    def get_queryset(self):
        return PolicyHolder.objects.annotate(
            numeric_id=Cast(Substr('policy_holder_id', 6), IntegerField())
        ).order_by('numeric_id')

class PolicyHolderDetailView(generics.RetrieveAPIView):
    queryset = PolicyHolder.objects.all()
    serializer_class = PolicyHolderSerializer