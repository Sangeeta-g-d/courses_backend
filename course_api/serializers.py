from rest_framework import serializers
from admin_part.models import Bundle, Enrollment

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
