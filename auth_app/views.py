from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import PasswordResetOTP
from courses_backend.api_response import APIResponseMixin
from rest_framework.permissions import IsAuthenticated,AllowAny
from course_api.utils import get_user_watch_time_rankings, get_user_rank
from admin_part.models import Enrollment, Course, UserProgress
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status as drf_status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from admin_part.models import LiveSession
from django.shortcuts import get_object_or_404
import jwt
import time
from rest_framework import status as drf_status
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
import os
from django.conf import settings  
import random  
from .models import CustomUser
from .serializers import *
User = get_user_model()


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
        user = request.user

        # --------------------------------------------------
        # 🔹 User basic profile
        # --------------------------------------------------
        serializer = UserDetailSerializer(user)
        user_data = serializer.data

        # --------------------------------------------------
        # 🔹 Profile stats
        # --------------------------------------------------
        bundles_enrolled_qs = Enrollment.objects.filter(
            user=user,
            is_active=True,
            payment_status__in=["completed", "free"]
        )

        completed_bundle_ids = bundles_enrolled_qs.filter(
            progress_percentage=100
        ).values_list("bundle_id", flat=True)

        total_watch_seconds = UserProgress.objects.filter(
            user=user
        ).aggregate(
            total=Sum("watched_duration")
        )["total"] or 0

        profile_stats = {
            "bundles_enrolled": bundles_enrolled_qs.count(),
            "bundles_completed": bundles_enrolled_qs.filter(
                progress_percentage=100
            ).count(),
            "courses_completed": Course.objects.filter(
                bundle_id__in=completed_bundle_ids,
                is_published=True
            ).count(),
            "lectures_completed": UserProgress.objects.filter(
                user=user,
                completed=True
            ).count(),
            "total_learning_hours": round(total_watch_seconds / 3600, 2)
        }

        # --------------------------------------------------
        # 🔹 Rankings
        # --------------------------------------------------
        top_users_raw = get_user_watch_time_rankings()[:5]

        top_users = []
        for item in top_users_raw:
            data = item.copy()
            if data.get("profile_image"):
                data["profile_image"] = request.build_absolute_uri(
                    data["profile_image"]
                )
            top_users.append(data)

        current_user_rank = get_user_rank(user)

        current_user_stats = user.progress.aggregate(
            total_watched_duration=Sum("watched_duration"),
            completed_lectures=Count(
                "lecture",
                filter=Q(completed=True)
            ),
            total_lectures=Count("lecture"),
        )

        rankings = {
            "top_users": top_users or [],
            "current_user_rank": current_user_rank,
            "current_user_stats": {
                "total_watch_time_minutes": int(
                    (current_user_stats["total_watched_duration"] or 0) / 60
                ),
                "completed_lectures": current_user_stats["completed_lectures"] or 0,
                "total_lectures": current_user_stats["total_lectures"] or 0,
            }
        }

        # --------------------------------------------------
        # 🔹 Final response payload
        # --------------------------------------------------
        response_data = {
            **user_data,
            "profile_stats": profile_stats,
            "rankings": rankings
        }

        return self.success_response(
            message="User details fetched successfully",
            data=response_data
        )

    # --------------------------------------------------
    # 🔹 Update full profile
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 🔹 Partial update
    # --------------------------------------------------
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
    


class LiveSessionListAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request):
        sessions = LiveSession.objects.all().order_by("-session_date", "-session_time")

        serializer = LiveSessionSerializer(
            sessions,
            many=True,
            context={"request": request}
        )

        return self.success_response(
            message="Live sessions fetched successfully",
            data={
                "total_sessions": sessions.count(),
                "sessions": serializer.data
            },
            status_code=drf_status.HTTP_200_OK
        )


class LiveSessionDetailAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)

        serializer = LiveSessionSerializer(
            session,
            context={"request": request}
        )

        return self.success_response(
            message="Live session details fetched successfully",
            data=serializer.data,
            status_code=drf_status.HTTP_200_OK
        )


class ZoomTokenGeneratorAPIView(APIView, APIResponseMixin):
    """
    Generate JWT token for Zoom SDK integration in Flutter/Web
    
    Endpoint: POST /api/auth/zoom-token/
    Requires: Authentication with Bearer token
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate Zoom JWT token for meeting access
        
        Request body:
        {
            "meeting_number": "string",
            "session_id": "integer (optional)",
            "user_display_name": "string",
            "role_type": "integer (optional, 0=attendee, 1=host, default=0)"
        }
        """
        serializer = ZoomTokenRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get validated data
            meeting_number = serializer.validated_data['meeting_number']
            user_display_name = serializer.validated_data['user_display_name']
            role_type = serializer.validated_data.get('role_type', 0)
            
            # Get Zoom credentials from settings/environment
            sdk_key = settings.ZOOM_SDK_KEY
            sdk_secret = settings.ZOOM_SDK_SECRET
            
            if not sdk_key or not sdk_secret:
                return self.error_response(
                    errors="Zoom SDK credentials not configured",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Calculate expiration (1 hour from now)
            now = int(time.time())
            expiration = now + 3600  # Token expires in 1 hour
            
            # Create JWT payload for Zoom
            payload = {
                "iss": sdk_key,              # Zoom SDK Key
                "exp": expiration,            # Expiration timestamp
                "aud": "zoom",                # Audience
                "iat": now,                   # Issued at
                "appKey": sdk_key,            # App key (same as iss)
                "tokenExp": expiration,       # Token expiration
                "tpc": meeting_number,        # Topic/Session name (required by SDK)
                "role_type": role_type        # User role: 0=attendee, 1=host (required by SDK)
            }
            
            # DEBUG: Log the payload to verify claims are included
            import sys
            print(f"🔵 Zoom JWT Payload: {payload}", file=sys.stderr)
            print(f"🔵 Meeting Number (tpc): {meeting_number}", file=sys.stderr)
            print(f"🔵 Role Type: {role_type}", file=sys.stderr)
            
            # Generate JWT token using HS256
            jwt_token = jwt.encode(
                payload,
                sdk_secret,
                algorithm='HS256'
            )
            
            # DEBUG: Decode and verify the token contains the claims
            decoded = jwt.decode(
                jwt_token, 
                sdk_secret, 
                algorithms=['HS256'],
                audience='zoom'  # Specify the expected audience
            )
            print(f"🔵 Decoded JWT Claims: {decoded}", file=sys.stderr)
            
            # Format expiration timestamp as ISO 8601
            expires_at = datetime.fromtimestamp(expiration).isoformat() + 'Z'
            
            response_data = {
                "jwt_token": jwt_token,
                "expires_in": 3600,           # Expiration in seconds
                "expires_at": expires_at,     # ISO 8601 timestamp
                "meeting_number": meeting_number,
                "role_type": role_type        # User role used in JWT
            }
            
            return self.success_response(
                message="Zoom token generated successfully",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            return self.error_response(
                errors=f"Error generating Zoom token: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# forgot password
class ForgotPasswordAPI(APIResponseMixin, APIView):

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return self.error_response("Email is required")

        try:
            user = User.objects.get(email=email)

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            reset_path = reverse(
                "reset_password_api",
                kwargs={"uidb64": uid, "token": token}
            )

            reset_link = request.build_absolute_uri(reset_path)

            send_mail(
                subject="Reset Your Password",
                message=f"""
Hello {user.full_name or user.email},

Click below link to reset your password:

{reset_link}

If you did not request this, ignore this email.
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )

            return self.success_response(
                message="Password reset link sent to your email"
            )

        except User.DoesNotExist:
            return self.error_response("Email not registered")
        

class ResetPasswordAPI(APIResponseMixin, APIView):

    def post(self, request, uidb64, token):

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            return self.error_response("Invalid reset link")

        if not default_token_generator.check_token(user, token):
            return self.error_response("Invalid or expired token")

        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        if not password or not confirm_password:
            return self.error_response("Password fields are required")

        if password != confirm_password:
            return self.error_response("Passwords do not match")

        user.set_password(password)
        user.save()

        return self.success_response(
            message="Password reset successful"
        )


# OTP-based Forgot Password APIs
class RequestOTPAPIView(APIResponseMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            if not CustomUser.objects.filter(email=email).exists():
                return self.error_response(message="User with this email does not exist", status_code=status.HTTP_400_BAD_REQUEST)
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            expires_at = timezone.now() + timedelta(minutes=10)
            
            # Invalidate old unused OTPs for this email
            PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)
            
            # Create new OTP
            PasswordResetOTP.objects.create(email=email, otp=otp, expires_at=expires_at)
            
            # Send email
            subject = 'Password Reset OTP'
            message = f'Your OTP for password reset is: {otp}. It expires in 10 minutes.'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            
            return self.success_response(message="OTP sent to your email", status_code=status.HTTP_200_OK)
        return self.error_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


class VerifyOTPAPIView(APIResponseMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']
            
            try:
                otp_obj = PasswordResetOTP.objects.get(email=email, otp=otp, is_used=False)
                if otp_obj.is_expired():
                    return self.error_response(message="OTP has expired", status_code=status.HTTP_400_BAD_REQUEST)
                
                otp_obj.is_used = True
                otp_obj.save()
                
                return self.success_response(message="OTP verified successfully", status_code=status.HTTP_200_OK)
            except PasswordResetOTP.DoesNotExist:
                return self.error_response(message="Invalid OTP", status_code=status.HTTP_400_BAD_REQUEST)
        return self.error_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


class ResetPasswordAPIView(APIResponseMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']
            
            try:
                otp_obj = PasswordResetOTP.objects.get(email=email, otp=otp, is_used=False)
                if otp_obj.is_expired():
                    return self.error_response(message="OTP has expired", status_code=status.HTTP_400_BAD_REQUEST)
                
                user = CustomUser.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                
                otp_obj.is_used = True
                otp_obj.save()
                
                return self.success_response(message="Password reset successfully", status_code=status.HTTP_200_OK)
            except PasswordResetOTP.DoesNotExist:
                return self.error_response(message="Invalid OTP", status_code=status.HTTP_400_BAD_REQUEST)
            except CustomUser.DoesNotExist:
                return self.error_response(message="User not found", status_code=status.HTTP_400_BAD_REQUEST)
        return self.error_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)




class AppVersionAPIView(APIView):

    def get(self, request):
        data = {
            "status": "200",
            "message": "App version metadata",
            "Response": {
                "latest_app_version": 2,
                "minimum_app_version": 1
            }
        }
        return Response(data, status=status.HTTP_200_OK)