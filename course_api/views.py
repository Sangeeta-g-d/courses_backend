from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.shortcuts import get_object_or_404
from rest_framework import status as drf_status
from admin_part.models import Bundle, Enrollment, Course
from .serializers import *
from courses_backend.api_response import APIResponseMixin
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.conf import settings
import razorpay


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
    


class BundleCoursesAPIView(APIView, APIResponseMixin):

    def get(self, request, bundle_id):
        try:
            bundle = Bundle.objects.get(id=bundle_id, is_published=True)
        except Bundle.DoesNotExist:
            return self.error_response(
                "Bundle not found",
                status_code=drf_status.HTTP_404_NOT_FOUND
            )

        courses = Course.objects.filter(
            bundle=bundle,
        ).order_by('-created_at')

        serializer = CourseSerializer(
            courses,
            many=True,
            context={'request': request}
        )

        return self.success_response(
            message="Courses fetched successfully",
            data={
                "bundle_id": bundle.id,
                "bundle_name": bundle.name,
                "total_courses": courses.count(),
                "courses": serializer.data
            }
        )
    
class BundleEnrollAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, bundle_id):
        user = request.user

        # 1️⃣ Validate bundle
        try:
            bundle = Bundle.objects.get(id=bundle_id, is_published=True)
        except Bundle.DoesNotExist:
            return self.error_response(
                "Bundle not found",
                status_code=drf_status.HTTP_404_NOT_FOUND
            )

        # 2️⃣ Check existing enrollment
        enrollment = Enrollment.objects.filter(
            user=user,
            bundle=bundle
        ).first()

        if enrollment and enrollment.payment_status in ['completed', 'free']:
            return self.success_response(
                message="Already enrolled in this bundle",
                data=EnrollmentSerializer(enrollment).data
            )

        # 3️⃣ Create enrollment if not exists
        if not enrollment:
            if bundle.is_free:
                payment_status = 'free'
                amount_paid = 0
            else:
                payment_status = 'pending'
                amount_paid = bundle.get_discounted_price()

            enrollment = Enrollment.objects.create(
                user=user,
                bundle=bundle,
                payment_status=payment_status,
                amount_paid=amount_paid
            )

        # 4️⃣ If FREE bundle → done
        if bundle.is_free:
            return self.success_response(
                message="Enrollment successful (Free bundle)",
                data={
                    "enrollment": EnrollmentSerializer(enrollment).data,
                    "is_free": True
                },
                status_code=drf_status.HTTP_201_CREATED
            )

        # 5️⃣ PAID bundle → Create Razorpay Order
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        amount_in_paise = int(enrollment.amount_paid * 100)

        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1
        })

        # 6️⃣ Store Razorpay Order ID
        enrollment.razorpay_order_id = razorpay_order["id"]
        enrollment.save(update_fields=["razorpay_order_id"])

        return self.success_response(
            message="Enrollment created & Razorpay order generated",
            data={
                "enrollment": EnrollmentSerializer(enrollment).data,
                "is_free": False,
                "razorpay": {
                    "razorpay_order_id": razorpay_order["id"],
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": amount_in_paise,
                    "currency": "INR"
                }
            },
            status_code=drf_status.HTTP_201_CREATED
        )
    

class VerifyRazorpayPaymentAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        enrollment_id = request.data.get("enrollment_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_signature = request.data.get("razorpay_signature")

        # 1️⃣ Validate payload
        if not all([
            enrollment_id,
            razorpay_payment_id,
            razorpay_order_id,
            razorpay_signature
        ]):
            return self.error_response(
                "Missing payment details",
                status_code=drf_status.HTTP_400_BAD_REQUEST
            )

        # 2️⃣ Validate enrollment
        try:
            enrollment = Enrollment.objects.get(
                id=enrollment_id,
                user=request.user,
                razorpay_order_id=razorpay_order_id,
                payment_status='pending'
            )
        except Enrollment.DoesNotExist:
            return self.error_response(
                "Invalid or already processed enrollment",
                status_code=drf_status.HTTP_400_BAD_REQUEST
            )

        # 3️⃣ Verify signature with Razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })
        except razorpay.errors.SignatureVerificationError:
            enrollment.payment_status = 'failed'
            enrollment.save(update_fields=["payment_status"])

            return self.error_response(
                "Payment verification failed",
                status_code=drf_status.HTTP_400_BAD_REQUEST
            )

        # 4️⃣ Payment success → store Razorpay data
        enrollment.razorpay_payment_id = razorpay_payment_id
        enrollment.razorpay_signature = razorpay_signature
        enrollment.payment_status = 'completed'
        enrollment.save(update_fields=[
            "razorpay_payment_id",
            "razorpay_signature",
            "payment_status"
        ])

        return self.success_response(
            message="Payment verified and enrollment completed",
            data={
                "enrollment_id": enrollment.id,
                "bundle_id": enrollment.bundle.id,
                "payment_status": enrollment.payment_status
            }
        )
    

# featured courses
class HomeFeaturedAPIView(APIView, APIResponseMixin):
    """
    Home page API:
    - Featured 5 bundles
    - Featured top 5 recent courses
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # 🔹 Featured Bundles (latest 5 published)
            featured_bundles = (
                Bundle.objects
                .filter(is_published=True)
                .order_by('-created_at')[:5]
            )

            # 🔹 Featured Recent Courses (latest 5 published)
            featured_courses = (
                Course.objects
                .filter(is_published=True)
                .select_related('bundle')
                .order_by('-created_at')[:5]
            )

            response_data = {
                "featured_bundles": FeaturedBundleSerializer(
                    featured_bundles, many=True, context={'request': request}
                ).data,
                "featured_courses": FeaturedCourseSerializer(
                    featured_courses, many=True, context={'request': request}
                ).data
            }

            return self.success_response(
                message="Home featured data fetched successfully",
                data=response_data
            )

        except Exception as e:
            return self.error_response(
                str(e),
                status_code=500
            )