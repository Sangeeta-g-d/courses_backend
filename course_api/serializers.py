from rest_framework import serializers
from admin_part.models import Bundle


class BundleSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = Bundle
        fields = [
            "id",
            "name",
            "slug",
            "price",
            "discount",
            "discounted_price",
            "is_free",
            "short_description",
            "full_description",
            "thumbnail_url",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def get_discounted_price(self, obj):
        return obj.get_discounted_price()
