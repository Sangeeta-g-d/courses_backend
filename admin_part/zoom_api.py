# zoom_api.py
import jwt
import time
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json

class ZoomSignatureAPIView(APIView):
    """
    Generate JWT signature for Zoom Web SDK
    """
    def post(self, request):
        try:
            print("🔵 [ZoomSignatureAPIView] Request received:", request.data)

            meeting_number = str(request.data.get("meetingNumber", "")).strip()
            role = int(request.data.get("role", 0))

            if not meeting_number:
                return Response(
                    {"error": "Meeting number is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            print(f"🟢 Generating signature for meeting {meeting_number}, role {role}")

            sdk_key = settings.ZOOM_SDK_KEY
            sdk_secret = settings.ZOOM_SDK_SECRET

            if not sdk_key or not sdk_secret:
                print("❌ Zoom SDK credentials not configured")
                return Response(
                    {"error": "Zoom SDK not configured"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Create JWT payload - CORRECT FORMAT for Zoom
            iat = int(time.time())
            exp = iat + 7200  # 2 hours
            
            payload = {
                "appKey": sdk_key,  # Use "appKey" instead of "sdkKey"
                "iat": iat,
                "exp": exp,
                "tokenExp": exp
            }

            print("📦 JWT payload:", payload)

            # Generate JWT token using pyjwt
            jwt_token = jwt.encode(
                payload,
                sdk_secret,
                algorithm="HS256"
            )

            # If jwt.encode returns bytes, decode to string
            if isinstance(jwt_token, bytes):
                jwt_token = jwt_token.decode('utf-8')

            print("✅ Signature successfully generated")
            print(f"🔑 Token length: {len(jwt_token)}")

            return Response({
                "signature": jwt_token,
                "sdkKey": sdk_key,
                "meetingNumber": meeting_number,
                "password": ""  # Add empty password if not required
            })

        except Exception as e:
            print(f"❌ Error generating signature: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": f"Internal error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )