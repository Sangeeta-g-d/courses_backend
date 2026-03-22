from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.shortcuts import get_object_or_404
from .pagination import PostPagination
from rest_framework import status as drf_status
from admin_part.models import Bundle, Enrollment, Course, Post
from admin_part.models import Banner
from user_part.utils import get_user_rank, get_user_watch_time_rankings
from .serializers import *
from courses_backend.api_response import APIResponseMixin
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.conf import settings
import razorpay
from django.db.models import Sum, Count, Q
import math



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
        # PAGINATION PARAMETERS
        # ---------------------------
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100  # Maximum limit to prevent performance issues
        except (ValueError, TypeError):
            page_size = 20

        # ---------------------------
        # FETCH BUNDLES
        # ---------------------------
        bundles_queryset = Bundle.objects.filter(is_published=True).annotate(
            total_courses=Count('courses')
        )

        # Calculate total items
        total_items = bundles_queryset.count()

        # Calculate pagination values
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Handle edge cases: page > totalPages or page < 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        # Slice the queryset
        paginated_bundles = bundles_queryset[start_index:end_index]

        serializer = BundleDetailSerializer(
            paginated_bundles,
            many=True,
            context={
                "request": request,
                "user": user
            }
        )

        # Build pagination metadata
        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

        return self.success_response(
            message="Bundles fetched successfully",
            data={
                "bundles": serializer.data,
                "pagination": pagination
            }
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

        # 🔹 Bundle media
        thumbnail_url = (
            request.build_absolute_uri(bundle.thumbnail.url)
            if bundle.thumbnail else None
        )

        preview_video_url = (
            request.build_absolute_uri(bundle.preview_video.url)
            if bundle.preview_video else None
        )

        bundle_pdf_url = (
            request.build_absolute_uri(bundle.bundle_pdf.url)
            if bundle.bundle_pdf else None
        )

        # 🔹 Auth check
        is_logged_in = request.user.is_authenticated

        is_enrolled = False
        purchase_type = None
        payment_status = None
        progress_percentage = 0
        has_pdf_access = False

        if is_logged_in:
            enrollment = Enrollment.objects.filter(
                user=request.user,
                bundle=bundle,
                is_active=True,
                payment_status__in=['completed', 'free']
            ).first()

            if enrollment:
                is_enrolled = True
                purchase_type = enrollment.purchase_type
                payment_status = enrollment.payment_status
                progress_percentage = enrollment.progress_percentage
                has_pdf_access = enrollment.has_pdf

        # 🔹 PDF info
        has_pdf = bool(bundle.bundle_pdf or bundle.bundle_pdf_price)
        pdf_price = bundle.bundle_pdf_price or None

        # 🔹 Fetch courses (ALWAYS fetch)
        courses = Course.objects.filter(
            bundle=bundle,
            is_published=True
        ).order_by('-created_at')

        course_serializer = CourseSerializer(
            courses,
            many=True,
            context={'request': request}
        )

        # =====================================================
        # 🔐 ACCESS CONTROL LOGIC (FINAL)
        # =====================================================
        show_courses = True
        show_pdf = False

        if not is_logged_in:
            # Public preview
            show_courses = True
            show_pdf = False

        elif is_logged_in and not is_enrolled:
            # Logged in but not purchased
            show_courses = True
            show_pdf = False

        elif is_enrolled:
            if purchase_type == "bundle":
                show_courses = True
                show_pdf = False

            elif purchase_type == "pdf":
                show_courses = False
                show_pdf = True

            elif purchase_type == "both":
                show_courses = True
                show_pdf = True

        # 🔹 Final PDF URL based on access
        pdf_url = bundle_pdf_url if show_pdf else None

        # =====================================================
        # 📦 RESPONSE DATA
        # =====================================================
        response_data = {
            "bundle_id": bundle.id,
            "bundle_name": bundle.name,
            "bundle_thumbnail": thumbnail_url,
            "bundle_preview_video": preview_video_url,

            "short_description": bundle.short_description,
            "full_description": bundle.full_description,

            "price": bundle.price,
            "discount": bundle.discount,
            "discounted_price": bundle.get_discounted_price(),
            "is_free": bundle.is_free,

            "is_logged_in": is_logged_in,
            "is_enrolled": is_enrolled,
            "purchase_type": purchase_type,
            "payment_status": payment_status,
            "progress_percentage": progress_percentage,

            "has_pdf": has_pdf,
            "has_purchased_pdf": has_pdf_access,
            "pdf_url": pdf_url,
            "pdf_price": pdf_price,

            "total_courses": courses.count() if show_courses else 0,
            "courses": course_serializer.data if show_courses else [],
        }

        # 🔹 Message
        if is_enrolled:
            if purchase_type == "pdf":
                message = "PDF access only"
            elif purchase_type == "both":
                message = "Courses + PDF access"
            else:
                message = "Course access"
        else:
            message = "Bundle preview data"

        return self.success_response(
            message=message,
            data=response_data
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

        # 2️⃣ Get purchase_type
        purchase_type = request.data.get("purchase_type", "bundle").lower()

        valid_purchase_types = ["bundle", "pdf", "both"]
        if purchase_type not in valid_purchase_types:
            return self.error_response(
                f"Invalid purchase_type. Must be one of: {valid_purchase_types}",
                status_code=drf_status.HTTP_400_BAD_REQUEST
            )

        # 3️⃣ Prices
        bundle_price = bundle.get_discounted_price() if not bundle.is_free else 0
        pdf_price = bundle.bundle_pdf_price or 0

        def calculate_amount(ptype):
            if ptype == "bundle":
                return bundle_price
            elif ptype == "pdf":
                return pdf_price
            elif ptype == "both":
                return bundle_price + pdf_price

        requested_amount = calculate_amount(purchase_type)

        # 4️⃣ Check existing enrollment
        enrollment = Enrollment.objects.filter(
            user=user,
            bundle=bundle,
            payment_status__in=["completed", "free"]
        ).first()

        is_upgrade = False

        # 5️⃣ Handle existing enrollment (UPGRADE LOGIC)
        if enrollment:
            old_type = enrollment.purchase_type

            # Already same purchase
            if old_type == purchase_type:
                return self.success_response(
                    message="Already enrolled with this purchase type",
                    data=EnrollmentSerializer(enrollment).data
                )

            # 🔥 Merge purchase types correctly
            if {old_type, purchase_type} == {"bundle", "pdf"}:
                new_type = "both"
            elif purchase_type == "both":
                new_type = "both"
            else:
                new_type = purchase_type

            new_amount = calculate_amount(new_type)
            old_amount = enrollment.amount_paid

            upgrade_amount = max(0, new_amount - old_amount)

            # Update enrollment
            enrollment.purchase_type = new_type
            enrollment.has_pdf = new_type in ["pdf", "both"]
            enrollment.amount_paid = upgrade_amount
            enrollment.payment_status = "pending"
            enrollment.razorpay_order_id = None
            enrollment.save(
                update_fields=[
                    "purchase_type",
                    "has_pdf",
                    "amount_paid",
                    "payment_status",
                    "razorpay_order_id"
                ]
            )

            is_upgrade = True
            amount_for_order = upgrade_amount

        else:
            # 6️⃣ New enrollment
            is_free_purchase = bundle.is_free and purchase_type == "bundle"

            payment_status = "free" if is_free_purchase else "pending"

            enrollment = Enrollment.objects.create(
                user=user,
                bundle=bundle,
                purchase_type=purchase_type,
                has_pdf=purchase_type in ["pdf", "both"],
                payment_status=payment_status,
                amount_paid=requested_amount
            )

            amount_for_order = requested_amount

        # 7️⃣ FREE enrollment
        if enrollment.payment_status == "free":
            return self.success_response(
                message="Enrollment successful (Free)",
                data={
                    "enrollment": EnrollmentSerializer(enrollment).data,
                    "is_free": True,
                    "is_upgrade": is_upgrade
                },
                status_code=drf_status.HTTP_201_CREATED
            )

        # 8️⃣ No payment required (upgrade = 0)
        if amount_for_order <= 0:
            enrollment.payment_status = "completed"
            enrollment.save(update_fields=["payment_status"])

            return self.success_response(
                message="Enrollment completed successfully",
                data={
                    "enrollment": EnrollmentSerializer(enrollment).data,
                    "is_free": True,
                    "is_upgrade": is_upgrade
                },
                status_code=drf_status.HTTP_201_CREATED
            )

        # 9️⃣ Razorpay Order Creation
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        amount_in_paise = int(amount_for_order * 100)

        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1
        })

        # 🔟 Save order id
        enrollment.razorpay_order_id = razorpay_order["id"]
        enrollment.save(update_fields=["razorpay_order_id"])

        return self.success_response(
            message="Enrollment created & Razorpay order generated",
            data={
                "enrollment": EnrollmentSerializer(enrollment).data,
                "is_free": False,
                "is_upgrade": is_upgrade,
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

            # 🔹 Continue Learning (top 2 for authenticated users)
            continue_learning = None
            if request.user.is_authenticated:
                continue_learning_items = (
                    UserProgress.objects
                    .filter(
                        user=request.user,
                        completed=False,
                        watched_duration__gt=0
                    )
                    .select_related(
                        'lecture',
                        'lecture__section',
                        'course'
                    )
                    .order_by('-last_watched')[:2]
                )
                
                if continue_learning_items.exists():
                    continue_learning = []
                    for progress in continue_learning_items:
                        lecture = progress.lecture
                        section = lecture.section
                        course = progress.course
                        
                        # Get thumbnail URL
                        thumbnail_url = None
                        if lecture.thumbnail:
                            thumbnail_url = request.build_absolute_uri(lecture.thumbnail.url)
                        
                        continue_learning.append({
                            "lecture_id": lecture.id,
                            "lecture_title": lecture.title,
                            "course_id": course.id,
                            "course_name": course.title,
                            "section_id": section.id,
                            "section_title": section.title,
                            "progress_percentage": progress.progress_percentage,
                            "thumbnail": thumbnail_url
                        })

            response_data = {
                "featured_bundles": FeaturedBundleSerializer(
                    featured_bundles, many=True, context={'request': request}
                ).data,
                "featured_courses": FeaturedCourseSerializer(
                    featured_courses, many=True, context={'request': request}
                ).data,
                "continue_learning": continue_learning
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
    permission_classes = []  # 🔥 allow unauthenticated access

    def get(self, request, section_id):
        # 1️⃣ Validate section
        section = get_object_or_404(
            CourseSection.objects.select_related('course__bundle'),
            id=section_id,
            course__is_published=True
        )

        user = request.user
        is_authenticated = user.is_authenticated
        is_enrolled = False

        # 2️⃣ Check enrollment only if authenticated
        if is_authenticated and section.course.bundle:
            is_enrolled = Enrollment.objects.filter(
                user=user,
                bundle=section.course.bundle,
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
                "is_authenticated": is_authenticated,
                "is_enrolled": is_enrolled
            }
        )

        # 4️⃣ Find last viewed lecture (most recent last_watched)
        last_viewed_lecture_id = None
        if is_authenticated:
            last_viewed = (
                UserProgress.objects
                .filter(
                    user=user,
                    lecture__section=section,
                    watched_duration__gt=0
                )
                .order_by('-last_watched')
                .only('lecture_id')
                .first()
            )
            if last_viewed:
                last_viewed_lecture_id = last_viewed.lecture_id

        message = (
            "Lectures fetched successfully"
            if is_authenticated
            else "Unauthenticated user. Login required to access full content"
        )

        return self.success_response(
            message=message,
            data={
                "section_id": section.id,
                "section_title": section.title,
                "bundle_id": section.course.bundle.id if section.course.bundle else None,
                "total_lectures": lectures.count(),
                "is_authenticated": is_authenticated,
                "is_enrolled": is_enrolled,
                "last_viewed_lecture_id": last_viewed_lecture_id,
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
        current_position = serializer.validated_data["current_position"]
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

        # 4️⃣ Handle video rewinding: Only update if moving forward (HANDLES SEEK/REWIND)
        # Cap current_position at total_duration to prevent over-counting
        new_position = min(current_position, progress.total_duration)
        
        # Only update if user has moved forward, ignore rewinds
        if new_position > progress.watched_duration:
            progress.watched_duration = new_position

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


class DashboardRankingAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 🔹 Top 5 users
        top_users_raw = get_user_watch_time_rankings()[:5]
        
        # Build absolute URLs for profile images
        top_users = []
        for user_data in top_users_raw:
            user_data_copy = user_data.copy()
            if user_data_copy.get("profile_image"):
                user_data_copy["profile_image"] = request.build_absolute_uri(user_data_copy["profile_image"])
            top_users.append(user_data_copy)

        # 🔹 Current user rank
        current_user_rank = get_user_rank(user)

        # 🔹 Current user stats
        current_user_stats = user.progress.aggregate(
            total_watched_duration=Sum('watched_duration'),
            completed_lectures=Count(
                'lecture',
                filter=Q(completed=True)
            ),
            total_lectures=Count('lecture')
        )

        response_data = {
            "top_users": top_users,
            "current_user_rank": current_user_rank,
            "current_user_stats": {
                "total_watch_time_minutes": int(
                    (current_user_stats["total_watched_duration"] or 0) / 60
                ),
                "completed_lectures": current_user_stats["completed_lectures"],
                "total_lectures": current_user_stats["total_lectures"],
            }
        }

        return self.success_response(
            message="Dashboard ranking data fetched successfully",
            data=response_data,
            status_code=drf_status.HTTP_200_OK
        )


class CourseListAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get query parameters with defaults and validation
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100  # Maximum limit to prevent performance issues
        except (ValueError, TypeError):
            page_size = 20

        # Get all published courses
        courses_queryset = Course.objects.filter(
            is_published=True
        ).prefetch_related(
            'course_sections',
            'course_sections__lectures'
        ).order_by('-created_at')

        # Calculate total items
        total_items = courses_queryset.count()

        # Calculate pagination values
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Handle edge cases: page > totalPages or page < 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        # Slice the queryset
        paginated_courses = courses_queryset[start_index:end_index]

        # Serialize the paginated courses
        serializer = CourseListSerializer(
            paginated_courses,
            many=True,
            context={'request': request}
        )

        # Build pagination metadata
        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

        return self.success_response(
            message="Courses fetched successfully",
            data={
                "courses": serializer.data,
                "pagination": pagination
            },
            status_code=drf_status.HTTP_200_OK
        )


class EnrolledBundleListAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get query parameters with defaults and validation
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100  # Maximum limit to prevent performance issues
        except (ValueError, TypeError):
            page_size = 20

        # Get all enrolled bundles for the user
        enrollments_queryset = Enrollment.objects.filter(
            user=request.user,
            is_active=True
        ).select_related(
            'bundle'
        ).prefetch_related(
            'bundle__courses'
        ).order_by('-enrolled_at')

        # Calculate total items
        total_items = enrollments_queryset.count()

        # Calculate pagination values
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Handle edge cases: page > totalPages or page < 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        # Slice the queryset
        paginated_enrollments = enrollments_queryset[start_index:end_index]

        serializer = EnrolledBundleSerializer(
            paginated_enrollments,
            many=True,
            context={'request': request}
        )

        # Build pagination metadata
        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

        return self.success_response(
            message="Enrolled bundles fetched successfully",
            data={
                "bundles": serializer.data,
                "pagination": pagination
            },
            status_code=drf_status.HTTP_200_OK
        )


# user profile stats
class UserProfileStatsAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 🔹 Bundles enrolled
        bundles_enrolled = Enrollment.objects.filter(
            user=user,
            is_active=True,
            payment_status__in=["completed", "free"]
        )

        total_bundles_enrolled = bundles_enrolled.count()

        # 🔹 Bundles completed
        bundles_completed = bundles_enrolled.filter(
            progress_percentage=100
        ).count()

        # 🔹 Courses completed
        # A course is considered completed if its bundle is completed
        completed_bundle_ids = bundles_enrolled.filter(
            progress_percentage=100
        ).values_list("bundle_id", flat=True)

        courses_completed = Course.objects.filter(
            bundle_id__in=completed_bundle_ids,
            is_published=True
        ).count()

        # 🔹 Lectures completed
        lectures_completed = UserProgress.objects.filter(
            user=user,
            completed=True
        ).count()

        # 🔹 Total learning time (seconds → hours)
        total_watch_seconds = UserProgress.objects.filter(
            user=user
        ).aggregate(
            total=Sum("watched_duration")
        )["total"] or 0

        total_learning_hours = round(total_watch_seconds / 3600, 2)

        data = {
            "bundles_enrolled": total_bundles_enrolled,
            "bundles_completed": bundles_completed,
            "courses_completed": courses_completed,
            "lectures_completed": lectures_completed,
            "total_learning_hours": total_learning_hours
        }

        return self.success_response(
            message="User profile statistics fetched successfully",
            data=data,
            status_code=drf_status.HTTP_200_OK
        )


class ContinueLearningAPIView(APIView, APIResponseMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get query parameters with defaults and validation
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100  # Maximum limit to prevent performance issues
        except (ValueError, TypeError):
            page_size = 20

        # Get all incomplete lectures for the user
        progress_queryset = (
            UserProgress.objects
            .filter(
                user=user,
                completed=False,
                watched_duration__gt=0
            )
            .select_related(
                'lecture',
                'lecture__section',
                'course'
            )
            .order_by('-last_watched')
        )

        # Calculate total items
        total_items = progress_queryset.count()

        # Calculate pagination values
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Handle edge cases: page > totalPages or page < 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        # Slice the queryset
        paginated_progress = progress_queryset[start_index:end_index]

        # Build lectures data
        lectures = []
        for progress in paginated_progress:
            lecture = progress.lecture
            section = lecture.section
            course = progress.course
            
            # Get thumbnail URL
            thumbnail_url = None
            if lecture.thumbnail:
                thumbnail_url = request.build_absolute_uri(lecture.thumbnail.url)
            
            lectures.append({
                "lecture_id": lecture.id,
                "lecture_title": lecture.title,
                "course_id": course.id,
                "course_name": course.title,
                "section_id": section.id,
                "section_title": section.title,
                "progress_percentage": progress.progress_percentage,
                "watched_duration_seconds": progress.watched_duration,
                "total_duration_seconds": progress.total_duration,
                "thumbnail": thumbnail_url
            })

        # Build pagination metadata
        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

        return self.success_response(
            message="Continue learning lectures fetched successfully",
            data={
                "lectures": lectures,
                "pagination": pagination
            },
            status_code=drf_status.HTTP_200_OK
        )


# class PostListAPIView(APIView, APIResponseMixin):

#     def get(self, request):
#         try:
#             posts = Post.objects.filter(
#                 is_active=True
#             ).order_by("-created_at")

#             serializer = PostSerializer(
#                 posts,
#                 many=True,
#                 context={"request": request}
#             )

#             return self.success_response(
#                 message="Posts fetched successfully",
#                 data=serializer.data
#             )

#         except Exception as e:
#             return self.error_response(str(e))
        


class PostListAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get query parameters with defaults and validation
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 20))
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100  # Maximum limit to prevent performance issues
        except (ValueError, TypeError):
            page_size = 20

        # Get all active posts
        posts_queryset = Post.objects.filter(
            is_active=True
        ).order_by('-created_at')

        # Calculate total items
        total_items = posts_queryset.count()

        # Calculate pagination values
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Handle edge cases: page > totalPages or page < 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        # Calculate slice indices
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        # Slice the queryset
        paginated_posts = posts_queryset[start_index:end_index]

        # Serialize the paginated posts
        serializer = PostSerializer(
            paginated_posts,
            many=True,
            context={'request': request}
        )

        # Build pagination metadata
        pagination = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

        return self.success_response(
            message="Posts fetched successfully",
            data={
                "posts": serializer.data,
                "pagination": pagination
            },
            status_code=drf_status.HTTP_200_OK
        )


class BannerListAPIView(APIView, APIResponseMixin):
    permission_classes = [AllowAny]

    def get(self, request):
        banners = Banner.objects.all().order_by("-created_at")
        serializer = BannerSerializer(banners, many=True, context={"request": request})
        return self.success_response(
            message="Banner images fetched successfully",
            data=serializer.data,
            status_code=drf_status.HTTP_200_OK,
        )