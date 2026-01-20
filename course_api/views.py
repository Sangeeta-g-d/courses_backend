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
    permission_classes = [AllowAny]

    def get(self, request, bundle_id):
        try:
            bundle = Bundle.objects.get(id=bundle_id, is_published=True)
        except Bundle.DoesNotExist:
            return self.error_response(
                "Bundle not found",
                status_code=drf_status.HTTP_404_NOT_FOUND
            )

        courses = Course.objects.filter(
            bundle=bundle
        ).order_by('-created_at')

        course_serializer = CourseSerializer(
            courses,
            many=True,
            context={'request': request}
        )

        # 🔹 Bundle thumbnail
        thumbnail_url = (
            request.build_absolute_uri(bundle.thumbnail.url)
            if bundle.thumbnail else None
        )

        # 🔐 Auth & Enrollment Check
        is_logged_in = request.user.is_authenticated
        is_enrolled = False
        enrollment_id = None
        payment_status = None
        progress_percentage = 0

        if is_logged_in:
            enrollment = Enrollment.objects.filter(
                user=request.user,
                bundle=bundle,
                is_active=True
            ).first()

            if enrollment:
                is_enrolled = True
                enrollment_id = enrollment.id
                payment_status = enrollment.payment_status
                progress_percentage = enrollment.progress_percentage

        return self.success_response(
            message="Courses fetched successfully",
            data={
                "bundle_id": bundle.id,
                "bundle_name": bundle.name,
                "bundle_thumbnail": thumbnail_url,
                "short_description": bundle.short_description,
                "full_description": bundle.full_description,
                "price": bundle.price,
                "discount": bundle.discount,
                "discounted_price": bundle.get_discounted_price(),
                "is_free": bundle.is_free,

                # 🔐 Auth info
                "is_logged_in": is_logged_in,
                "is_enrolled": is_enrolled,

                # 🎓 Enrollment details (only if enrolled)
                "enrollment_id": enrollment_id,
                "payment_status": payment_status,
                "progress_percentage": progress_percentage,

                "total_courses": courses.count(),
                "courses": course_serializer.data,
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
        

class CourseSectionsAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        try:
            course = Course.objects.select_related('bundle').get(
                id=course_id,
                is_published=True
            )
        except Course.DoesNotExist:
            return self.error_response(
                "Course not found",
                status_code=drf_status.HTTP_404_NOT_FOUND
            )

        sections = course.course_sections.prefetch_related('lectures').order_by('order')

        section_serializer = CourseSectionSerializer(
            sections,
            many=True,
            context={'request': request}
        )

        # 🔹 Course thumbnail
        course_thumbnail = (
            request.build_absolute_uri(course.thumbnail.url)
            if course.thumbnail else None
        )

        # 🔹 Preview video
        preview_video = (
            request.build_absolute_uri(course.preview_video.url)
            if course.preview_video else None
        )

        # -------------------------------
        # USER-AWARE PROGRESS
        # -------------------------------
        course_progress = None
        completed_lectures = None
        total_lectures = None
        is_enrolled = False

        if request.user.is_authenticated:
            is_enrolled = Enrollment.objects.filter(
                user=request.user,
                bundle=course.bundle,
                payment_status__in=['completed', 'free'],
                is_active=True
            ).exists()

            progress_qs = UserProgress.objects.filter(
                user=request.user,
                course=course
            )

            total_lectures = progress_qs.count()
            completed_lectures = progress_qs.filter(completed=True).count()

            course_progress = progress_qs.aggregate(
                avg_progress=Avg('progress_percentage')
            )['avg_progress']

            course_progress = int(course_progress) if course_progress else 0

        return self.success_response(
            message="Course sections fetched successfully",
            data={
                "course_id": course.id,
                "course_name": course.title,
                "course_thumbnail": course_thumbnail,
                "preview_video": preview_video,
                "is_enrolled": is_enrolled,
                "course_progress": course_progress,
                "completed_lectures": completed_lectures,
                "total_lectures": total_lectures,
                "total_sections": sections.count(),
                "sections": section_serializer.data
            }
        )


# lecture detail API can be added later
class SectionLectureListAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, section_id):
        # 1️⃣ Validate section
        section = get_object_or_404(
            CourseSection,
            id=section_id,
            course__is_published=True
        )

        # 2️⃣ Check enrollment for bundle
        bundle = section.course.bundle
        is_enrolled = False

        if bundle:
            is_enrolled = Enrollment.objects.filter(
                user=request.user,
                bundle=bundle,
                is_active=True,
                payment_status__in=['completed', 'free']
            ).exists()

        # 3️⃣ Fetch lectures
        lectures = Lecture.objects.filter(
            section=section
        ).order_by("order")

        serializer = LectureListSerializer(
            lectures,
            many=True,
            context={
                "request": request,
                "is_enrolled": is_enrolled
            }
        )

        return self.success_response(
            message="Lectures fetched successfully",
            data={
                "section_id": section.id,
                "section_title": section.title,
                "total_lectures": lectures.count(),
                "is_enrolled": is_enrolled,
                "lectures": serializer.data
            },
            status_code=drf_status.HTTP_200_OK
        )

class UpdateUserProgressAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = UserProgressUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(serializer.errors)

        lecture_id = serializer.validated_data["lecture_id"]
        watched_seconds = serializer.validated_data["watched_seconds"]
        user = request.user

        # 1️⃣ Validate lecture
        try:
            lecture = Lecture.objects.select_related(
                "section__course"
            ).get(id=lecture_id)
        except Lecture.DoesNotExist:
            return self.error_response(
                "Lecture not found",
                status_code=drf_status.HTTP_404_NOT_FOUND
            )

        course = lecture.section.course

        # 2️⃣ Get or create progress row
        progress, created = UserProgress.objects.get_or_create(
            user=user,
            lecture=lecture,
            defaults={
                "course": course,
                "total_duration": lecture.duration or 0
            }
        )

        # 3️⃣ Skip update if already completed (IMPORTANT)
        if progress.completed:
            return self.success_response(
                message="Lecture already completed",
                data={
                    "lecture_id": lecture.id,
                    "progress_percentage": progress.progress_percentage,
                    "completed": True
                }
            )

        # 4️⃣ Increment watched duration (CAP at total duration)
        progress.watched_duration = min(
            progress.total_duration,
            progress.watched_duration + watched_seconds
        )

        # 5️⃣ Save ONLY required fields (performance critical)
        progress.save(update_fields=[
            "watched_duration",
            "progress_percentage",
            "completed",
            "completed_at",
            "last_watched"
        ])

        return self.success_response(
            message="Progress updated",
            data={
                "lecture_id": lecture.id,
                "watched_duration": progress.watched_duration,
                "progress_percentage": round(progress.progress_percentage, 2),
                "completed": progress.completed
            },
            status_code=drf_status.HTTP_200_OK
        )
