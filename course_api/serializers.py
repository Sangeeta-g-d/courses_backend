from rest_framework import serializers
from admin_part.models import Bundle, Enrollment,Course

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
                payment_status__in=["completed", "free"],
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
            'created_at',
        ]

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None
