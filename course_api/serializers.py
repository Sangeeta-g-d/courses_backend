from rest_framework import serializers
from admin_part.models import Bundle, CourseSection, Enrollment,Course, UserProgress, Lecture
from django.db.models import Avg

class BundleDetailSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    already_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Bundle
        fields = [
            "id",
            "name",
            "price",
            "discount",
            "discounted_price",
            "is_free",
            "short_description",
            "full_description",
            "thumbnail_url",
            "already_enrolled",
            "is_published",
            "created_at",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    def get_already_enrolled(self, obj):
        user = self.context.get("user")

        if user and user.is_authenticated:
            return Enrollment.objects.filter(
                user=user,
                bundle=obj,
                payment_status__in=["completed", "free"],  # ONLY FINAL STATES
                is_active=True
            ).exists()

        return False


class CourseSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    preview_video_url = serializers.SerializerMethodField()
    total_duration = serializers.ReadOnlyField(source='calculated_total_duration_display')
    total_lectures = serializers.ReadOnlyField(source='calculated_total_lectures')

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'short_description',
            'full_description',
            'language',
            'level',
            'thumbnail_url',
            'preview_video_url',
            'total_duration',
            'total_lectures',
            'created_at',
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_preview_video_url(self, obj):
        request = self.context.get('request')
        if obj.preview_video and request:
            return request.build_absolute_uri(obj.preview_video.url)
        return None
    

class EnrollmentSerializer(serializers.ModelSerializer):
    bundle_name = serializers.CharField(source='bundle.name', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'bundle',
            'bundle_name',
            'payment_status',
            'amount_paid',
            'progress_percentage',
            'enrolled_at'
        ]


# featured bundles serializer
class FeaturedBundleSerializer(serializers.ModelSerializer):
    discounted_price = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Bundle
        fields = [
            'id',
            'name',
            'price',
            'discount',
            'discounted_price',
            'is_free',
            'short_description',
            'thumbnail',
        ]

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None


# feature courses serializer
class FeaturedCourseSerializer(serializers.ModelSerializer):
    bundle_name = serializers.CharField(source='bundle.name', read_only=True)
    total_duration = serializers.CharField(
        source='calculated_total_duration_display',
        read_only=True
    )
    total_lectures = serializers.IntegerField(
        source='calculated_total_lectures',
        read_only=True
    )
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'thumbnail',
            'short_description',
            'language',
            'level',
            'bundle_name',
            'total_duration',
            'total_lectures',
        ]

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None



class CourseSectionSerializer(serializers.ModelSerializer):
    total_duration_display = serializers.ReadOnlyField(
        source='calculated_total_duration_display'
    )
    thumbnail = serializers.SerializerMethodField()
    section_progress = serializers.SerializerMethodField()

    class Meta:
        model = CourseSection
        fields = [
            'id',
            'title',
            'order',
            'total_lectures',
            'total_duration_display',
            'thumbnail',
            'section_progress',
        ]

    def get_thumbnail(self, obj):
        """
        Section thumbnail → first lecture thumbnail (fallback)
        """
        request = self.context.get('request')

        lecture = obj.lectures.filter(thumbnail__isnull=False).first()
        if lecture and lecture.thumbnail and request:
            return request.build_absolute_uri(lecture.thumbnail.url)

        return None

    def get_section_progress(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return None

        progress = UserProgress.objects.filter(
            user=request.user,
            lecture__section=obj
        ).aggregate(avg_progress=Avg('progress_percentage'))['avg_progress']

        return int(progress) if progress is not None else 0
    

# lectures
class LectureListSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    is_watched = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Lecture
        fields = [
            "id",
            "title",
            "duration",
            "video_url",
            "is_preview",
            "order",
            "processing_status",
            "is_watched",
            "progress_percentage",
            "thumbnail",
            "resource",
        ]

    def get_video_url(self, obj):
        is_authenticated = self.context.get("is_authenticated", False)
        is_enrolled = self.context.get("is_enrolled", False)

        if not is_authenticated:
            return None

        if obj.is_preview or is_enrolled:
            return obj.video_url

        return None

    def get_is_watched(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return False

        progress = UserProgress.objects.filter(
            user=user,
            lecture=obj
        ).only("completed").first()

        return progress.completed if progress else False

    def get_progress_percentage(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return 0

        progress = UserProgress.objects.filter(
            user=user,
            lecture=obj
        ).only("progress_percentage").first()

        return progress.progress_percentage if progress else 0


class UserProgressUpdateSerializer(serializers.Serializer):
    lecture_id = serializers.IntegerField()
    watched_seconds = serializers.FloatField(min_value=1)


# all courses 
class CourseListSerializer(serializers.ModelSerializer):
    total_sections = serializers.IntegerField(source='course_sections.count', read_only=True)
    total_duration_seconds = serializers.IntegerField(
        source='calculated_total_duration',
        read_only=True
    )
    total_duration_display = serializers.CharField(
        source='calculated_total_duration_display',
        read_only=True
    )
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'thumbnail',
            'total_sections',
            'total_duration_seconds',
            'total_duration_display',
        ]

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None
    

# enrolled bundles

class EnrolledBundleSerializer(serializers.ModelSerializer):
    bundle_id = serializers.IntegerField(source='bundle.id', read_only=True)
    bundle_name = serializers.CharField(source='bundle.name', read_only=True)
    thumbnail = serializers.SerializerMethodField()
    total_courses = serializers.IntegerField(
        source='bundle.courses.count',
        read_only=True
    )
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'bundle_id',
            'bundle_name',
            'thumbnail',
            'total_courses',
            'payment_status',
            'amount_paid',
            'discounted_price',
            'progress_percentage',
            'enrolled_at',
        ]

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.bundle.thumbnail and request:
            return request.build_absolute_uri(obj.bundle.thumbnail.url)
        return None

    def get_discounted_price(self, obj):
        return obj.bundle.get_discounted_price()