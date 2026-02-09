from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from courses_backend.api_response import APIResponseMixin
from rest_framework.permissions import IsAuthenticated,AllowAny
from course_api.utils import get_user_watch_time_rankings, get_user_rank
from admin_part.models import Enrollment, Course, UserProgress
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from admin_part.models import LiveSession
from django.shortcuts import get_object_or_404
import jwt
import time
import os
from django.conf import settings  

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
    

from rest_framework import status as drf_status

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
                    message="Zoom SDK credentials not configured",
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
            decoded = jwt.decode(jwt_token, sdk_secret, algorithms=['HS256'])
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
                message=f"Error generating Zoom token: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )