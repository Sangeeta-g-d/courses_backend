from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import CustomUser, UserProfile
from django.utils import timezone
from datetime import datetime
from zoneinfo import ZoneInfo
from admin_part.models import LiveSession

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



class LiveSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField()
    session_datetime_ist = serializers.SerializerMethodField()
    session_time_ist = serializers.SerializerMethodField()

    class Meta:
        model = LiveSession
        fields = [
            "id",
            "title",
            "agenda",
            "thumbnail",
            "meeting_number",
            "Passcode",
            "meeting_url",
            "session_date",
            "session_time",
            "session_time_ist",
            "session_datetime_ist",
            "is_active",
            "created_at",
        ]

    def get_session_datetime_ist(self, obj):
        """
        Returns: '03 Feb 2026, 06:00 PM IST'
        """
        ist = ZoneInfo("Asia/Kolkata")
        session_dt = datetime.combine(
            obj.session_date,
            obj.session_time
        ).replace(tzinfo=ist)

        return session_dt.strftime("%d %b %Y, %I:%M %p IST")

    def get_session_time_ist(self, obj):
        """
        Returns: '06:00 PM'
        """
        ist = ZoneInfo("Asia/Kolkata")
        session_dt = datetime.combine(
            obj.session_date,
            obj.session_time
        ).replace(tzinfo=ist)

        return session_dt.strftime("%I:%M %p")


# Zoom Token Request Serializer
class ZoomTokenRequestSerializer(serializers.Serializer):
    meeting_number = serializers.CharField(required=True, help_text="Zoom meeting number")
    session_id = serializers.IntegerField(required=False, allow_null=True, help_text="Optional session ID")
    user_display_name = serializers.CharField(required=True, help_text="User's display name for the meeting")
    role_type = serializers.IntegerField(required=False, default=0, help_text="User role: 0=attendee, 1=host")

    def validate_meeting_number(self, value):
        """Validate that the meeting number exists and is active"""
        if not value.isdigit():
            raise serializers.ValidationError("Meeting number must contain only digits")
        
        # Check if the meeting exists in live sessions
        try:
            LiveSession.objects.get(meeting_number=value)
        except LiveSession.DoesNotExist:
            raise serializers.ValidationError("Meeting not found")
        
        return value

    def validate_role_type(self, value):
        """Validate role_type is either 0 (attendee) or 1 (host)"""
        if value not in [0, 1]:
            raise serializers.ValidationError("role_type must be 0 (attendee) or 1 (host)")
        return value

    def validate_user_display_name(self, value):
        """Validate user display name"""
        if len(value.strip()) == 0:
            raise serializers.ValidationError("User display name cannot be empty")
        if len(value) > 100:
            raise serializers.ValidationError("User display name is too long (max 100 characters)")
        return value.strip()