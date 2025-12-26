from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework import status
from admin_part.models import Bundle
from .serializers import BundleSerializer
from courses_backend.api_response import APIResponseMixin


class PublishedBundleListAPIView(APIResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            bundles = Bundle.objects.filter(is_published=True).order_by("-created_at")

            serializer = BundleSerializer(
                bundles,
                many=True,
                context={"request": request}
            )

            return self.success_response(
                message="Published bundles fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            return self.error_response(
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
