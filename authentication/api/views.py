from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated

from authentication.api.serializer import AuthSerializer,LoginSerializer, StaffSerializer, StaffAuditSerializer
from authentication.models import CustomUser
class AuthView(APIView):

    @swagger_auto_schema(
        operation_description="Register a Customer user ",
        request_body=AuthSerializer,
        responses={},
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        serializer = AuthSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"msg": "Account created"},
                status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {"error": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

class LoginView(APIView):
    @swagger_auto_schema(
        operation_description="Login a Customer user ",
        request_body=LoginSerializer,
        responses={},
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": token.key,
                "user": {
                    "id": user.user_id,
                    "email": user.email,
                    "role": user.role,
                }
            })
        else:
            return Response(
                {"error": serializer.errors},
                status.HTTP_400_BAD_REQUEST,
            )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Logout a Customer user ",
        responses={},
        tags=["Authentication"],
    )

    def post(self, request):
        try:
            # Delete the current user's token
            request.user.auth_token.delete()
            print(request.user.auth_token)
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Token.DoesNotExist:
            return Response({"detail": "Token not found."}, status=status.HTTP_400_BAD_REQUEST)

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get Logged in user details",
        responses={},
        tags=["Authentication"],
    )
    def get(self,request):
        user = request.user
        if user:
            return Response(
            data={
                "full_name":user.full_name,
                "email":user.email,
                "role":user.role,
                "department":user.department,
            },
            status=status.HTTP_200_OK,
        )
        return Response(status=status.HTTP_404_NOT_FOUND)

class StaffListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff_roles = ["Admin", "Manager", "Claim Adjuster"]
        staff_users = CustomUser.object.filter(role__in=staff_roles)
        serializer = StaffSerializer(staff_users, many=True)
        return Response(serializer.data)

class StaffDetailView(generics.RetrieveUpdateAPIView):
    queryset = CustomUser.object.all()
    serializer_class = StaffAuditSerializer




