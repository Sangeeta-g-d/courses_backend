from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from courses_backend.api_response import APIResponseMixin
from rest_framework.permissions import IsAuthenticated,AllowAny

class RegisterAPIView(APIResponseMixin, APIView):
    permission_classes = []  # AllowAny

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            data = {
                "user": {
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "role": user.role,
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }

            return self.success_response(
                message="Registration successful",
                data=data,
                status_code=status.HTTP_201_CREATED
            )

        return self.error_response(
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class UserProfileAPIView(APIResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        profile, created = UserProfile.objects.get_or_create(user=user)

        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()

            return self.success_response(
                message="Profile created successfully" if created else "Profile updated successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        return self.error_response(
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    

class LoginAPIView(APIResponseMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']

            refresh = RefreshToken.for_user(user)

            data = {
                "user": {
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "role": user.role,
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }

            return self.success_response(
                message="Login successful",
                data=data,
                status_code=status.HTTP_200_OK
            )

        return self.error_response(
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    

class FetchUserProfileAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return self.success_response(
            message="User details fetched successfully",
            data=serializer.data
        )

    def put(self, request):
        serializer = UserDetailSerializer(
            request.user,
            data=request.data,
            partial=False
        )

        if serializer.is_valid():
            serializer.save()
            return self.success_response(
                message="User details updated successfully",
                data=serializer.data
            )

        return self.error_response(serializer.errors)

    def patch(self, request):
        serializer = UserDetailSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return self.success_response(
                message="User details updated successfully",
                data=serializer.data
            )

        return self.error_response(serializer.errors)
    

# dashboard api view
