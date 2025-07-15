from drf_yasg.utils import swagger_auto_schema
from datetime import date, time

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from  rest_framework import  status, generics, viewsets
from rest_framework.permissions import IsAuthenticated

from claim.models import Claim
from authentication.permissions import IsAdmin, IsManager, IsClaimAdjuster
from  .serializer import ClaimSerializer, ClaimDetailSerializer

from policy_holder.models import PolicySubscription

# class ClaimView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     @swagger_auto_schema(
#         operation_description="Login a Customer user ",
#         request_body=ClaimSerializer,
#         responses={},
#     )
#     def post(self,request):
#         serializer = ClaimSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return  Response(
#                 data=serializer.data,
#                 status=status.HTTP_201_CREATED
#             )
#         else:
#             return Response(
#                 {"error": serializer.errors},
#                 status.HTTP_400_BAD_REQUEST,
#             )


class ClaimListView(generics.ListCreateAPIView):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer

class ClaimUpdateView(generics.UpdateAPIView):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer

class ClaimDeleteView(generics.DestroyAPIView):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer

class ClaimDetailView(APIView):
    def get(self, request, pk):
        try:
            instance = Claim.objects.select_related("policy_holder", "policy").get(pk=pk)
        except Claim.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        subscription = PolicySubscription.objects.filter(
            policy=instance.policy,
            policy_holder=instance.policy_holder
        ).first()
        print(subscription)
        formatted_date = instance.incident_date.strftime('%Y-%m-%d')  # '2024-07-14'
        formatted_time = instance.incident_time.strftime('%I:%M %p')  # '09:30 AM'

        data = {
            "claim_id": instance.claim_id,
            "claimant_name": instance.full_name,
            "policy_id": instance.policy.policy_id,
            "tags": instance.tags,

            "claim overview" : {
                "claim_type": instance.claim_type,
                "date_submitted": instance.created_at,
                "date_and_time_of_incident":f"{formatted_date,formatted_time}",
                "incident_location":instance.location_of_incident,
                "incident_description":instance.description,
                "images":instance.images.url,

            },

            "policy holder":{
                "policy_holder_id":instance.policy_holder.policy_holder_id,
                "full_name":instance.policy_holder.full_name,
                "email":instance.policy_holder.email,
                "phone_number":"",
                "address":"",

            },
            "policy":{
                "policy_id":instance.policy.policy_id,
                "status":getattr(subscription,"status",""),
                "coverage":instance.policy.coverage,
                "policy_start":getattr(subscription,"start_date",""),
                "policy_end":getattr(subscription,"next_renewal_date","")

            }
        }
        return  Response(data,status=status.HTTP_200_OK)

class ClaimViewSet(viewsets.ModelViewSet):
    '''
    Viewset that provide action for claim Action
    '''
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer

    @action(detail=False)
    def approve(self):
        pass

    def reject(self):
        pass

    def escalate(self):
        pass

    def follow_up_question(self):
        pass

    def edit_ai_information(self):
        pass