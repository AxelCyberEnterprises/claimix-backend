from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from authentication.api.serializer import AuthSerializer,LoginSerializer


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
                status.HTTP_200_OK,
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
