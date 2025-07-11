from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.api.serializer import AuthSerializer


class AuthView(APIView):

    @swagger_auto_schema(
        operation_description="Register a Customer user ",
        request_body=AuthSerializer,
        responses={
            200: "OTP sent successfully",
            400: "OTP not sent successfully",
        },
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
