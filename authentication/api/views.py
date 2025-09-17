from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404

from authentication.api.serializer import (
    AuthSerializer, 
    LoginSerializer, 
    StaffSerializer, 
    StaffAuditSerializer,
    StaffRoleUpdateSerializer
)
from authentication.models import CustomUser
from authentication.permissions import IsAdmin
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
        staff_users = CustomUser.objects.filter(role__in=staff_roles)
        serializer = StaffSerializer(staff_users, many=True)
        return Response(serializer.data)

class StaffDetailView(generics.RetrieveAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = StaffAuditSerializer
    lookup_field = 'user_id'

@swagger_auto_schema(
    method='patch',
    operation_description="Update a staff member's role, status, or department",
    request_body=StaffRoleUpdateSerializer,
    responses={
        200: StaffAuditSerializer(),
        400: "Invalid input",
        403: "Forbidden - Only administrators can update staff roles",
        404: "Staff member not found"
    },
    tags=["Staff"]
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def update_staff_role(request, user_id):
    """
    Update a staff member's role, status, or department.
    Only administrators can perform this action.
    """
    # Get the target user
    staff_member = get_object_or_404(CustomUser, user_id=user_id)
    
    # Check if the target user is a staff member
    if not staff_member.is_staff:
        return Response(
            {"detail": "The specified user is not a staff member"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if the user is trying to modify their own role
    if staff_member == request.user:
        return Response(
            {"detail": "You cannot modify your own role"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Serialize and validate the request data
    serializer = StaffRoleUpdateSerializer(
        instance=staff_member,
        data=request.data,
        context={'request': request},
        partial=True  # Allow partial updates
    )
    
    if serializer.is_valid():
        # Save the changes
        updated_staff = serializer.save()
        
        # Return the updated staff member
        response_serializer = StaffAuditSerializer(updated_staff)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
