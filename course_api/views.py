from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.shortcuts import get_object_or_404

from admin_part.models import Bundle, Enrollment
from .serializers import BundleDetailSerializer
from courses_backend.api_response import APIResponseMixin


class BundleListAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]
    authentication_classes = []  # handled manually

    def get(self, request):
        user = None

        # ---------------------------
        # OPTIONAL JWT AUTH (FIXED)
        # ---------------------------
        jwt_auth = JWTAuthentication()

        try:
            auth_result = jwt_auth.authenticate(request)
            if auth_result:
                user, token = auth_result
        except (InvalidToken, TokenError):
            # IMPORTANT: do NOT block bundle list
            user = None

        # ---------------------------
        # FETCH BUNDLES
        # ---------------------------
        bundles = Bundle.objects.filter(is_published=True)

        serializer = BundleDetailSerializer(
            bundles,
            many=True,
            context={
                "request": request,
                "user": user
            }
        )

        return self.success_response(
            message="Bundles fetched successfully",
            data=serializer.data
        )