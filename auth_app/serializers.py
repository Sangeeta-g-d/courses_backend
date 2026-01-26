from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import CustomUser, UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = (
            'full_name',
            'email',
            'phone_number',
            'profile_image',
            'password',
            'confirm_password',
        )
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        validated_data.pop('confirm_password')

        user = CustomUser.objects.create(
            full_name=validated_data.get('full_name'),
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number'),
            profile_image=validated_data.get('profile_image'),
            password=make_password(validated_data['password']),
            role='student',
            is_active=True,
        )
        return user


# user profile serializer 
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = (
            'dob',
            'highest_qualification',
            'city',
        )

# login 
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError("Email and password are required")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password")

        if not user.is_active:
            raise serializers.ValidationError("Account is disabled")

        attrs['user'] = user
        return attrs


# user profile
class FetchUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "dob",
            "highest_qualification",
            "city",
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    profile = FetchUserProfileSerializer(required=False, allow_null=True)
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",           # read-only
            "full_name",
            "phone_number",
            "profile_image",
            "role",
            "profile",
        ]

    def to_representation(self, instance):
        """Ensure profile is always included in response, even if null"""
        data = super().to_representation(instance)
        
        # Always include profile field (null if doesn't exist)
        if 'profile' not in data:
            data['profile'] = None
        
        return data

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)

        # Update CustomUser fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create profile
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance