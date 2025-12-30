from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.shortcuts import get_object_or_404

from admin_part.models import Bundle, Enrollment
from .serializers import BundleDetailSerializer
from courses_backend.api_response import APIResponseMixin


class BundleDetailAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]
    authentication_classes = []  # handled manually

    def get(self, request, slug):
        user = None
        already_enrolled = False

        # ---------------------------
        # OPTIONAL JWT AUTH HANDLING
        # ---------------------------
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(
                    jwt_auth.get_raw_token(auth_header.split()[1])
                )
                user = jwt_auth.get_user(validated_token)

            except (InvalidToken, TokenError):
                return self.error_response(
                    "Access token is expired or invalid",
                    status_code=401
                )

        # ---------------------------
        # FETCH BUNDLE
        # ---------------------------
        bundle = get_object_or_404(Bundle, slug=slug, is_published=True)

        serializer = BundleDetailSerializer(
            bundle,
            context={"request": request}
        )

        response_data = serializer.data

        # ---------------------------
        # ENROLLMENT CHECK
        # ---------------------------
        if user and user.is_authenticated:
            already_enrolled = Enrollment.objects.filter(
                user=user,
                bundle=bundle,
                payment_status__in=["completed", "free"]
            ).exists()

            response_data["already_enrolled"] = already_enrolled

        return self.success_response(
            message="Bundle details fetched successfully",
            data=response_data
        )
