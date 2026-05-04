# zoom_api.py
import jwt
import time
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json

class ZoomOAuthManager:
    """
    Manages Zoom OAuth token generation and API calls
    """
    TOKEN_URL = "https://zoom.us/oauth/token"
    API_BASE_URL = "https://api.zoom.us/v2"
    
    def __init__(self):
        self.account_id = settings.ZOOM_ACCOUNT_ID
        self.client_id = settings.ZOOM_CLIENT_ID
        self.client_secret = settings.ZOOM_CLIENT_SECRET
        self.access_token = None
        self.token_expiry = None
    
    def is_token_expired(self):
        """Check if token is expired (with 60 second buffer)"""
        if not self.access_token or not self.token_expiry:
            return True
        
        # Refresh if expires in less than 60 seconds
        return time.time() >= (self.token_expiry - 60)
    
    def get_access_token(self, force_refresh=False):
        """
        Get OAuth access token with automatic caching and refresh
        
        Args:
            force_refresh (bool): Force token refresh regardless of expiry
        
        Returns:
            str: Valid access token
        """
        try:
            # Return cached token if still valid
            if not force_refresh and self.access_token and not self.is_token_expired():
                print("[Zoom OAuth] ✓ Using cached access token")
                return self.access_token
            
            print("[Zoom OAuth] Generating new access token...")
            
            auth = (self.client_id, self.client_secret)
            payload = {
                'grant_type': 'account_credentials',
                'account_id': self.account_id
            }
            
            response = requests.post(self.TOKEN_URL, auth=auth, data=payload)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data['access_token']
            self.token_expiry = time.time() + data.get('expires_in', 3600)
            
            # Log scopes if available
            scopes = data.get('scope', '').split(' ') if data.get('scope') else []
            print(f"[Zoom OAuth] ✓ New token generated (expires in {data.get('expires_in')} seconds)")
            if scopes:
                print(f"[Zoom OAuth] Available scopes: {', '.join(scopes)}")
            
            return self.access_token
            
        except Exception as e:
            print(f"[Zoom OAuth] ❌ Error generating access token: {str(e)}")
            raise
    
    def refresh_token(self):
        """Force token refresh (use after adding new scopes)"""
        print("[Zoom OAuth] 🔄 Force refreshing token with new scopes...")
        return self.get_access_token(force_refresh=True)
    
    def create_meeting(self, topic, start_time, duration=60, settings_dict=None, session_type='webinar'):
        """
        Create a Zoom webinar or meeting
        
        Args:
            topic (str): Webinar/Meeting title
            start_time (str): ISO format datetime (e.g., "2024-02-10T10:00:00")
            duration (int): Duration in minutes (default 60)
            settings_dict (dict): Additional webinar settings
            session_type (str): 'webinar' or 'meeting' (default 'webinar' - privacy-first)
        
        Returns:
            dict: Webinar details including id, join_url, passcode
        """
        try:
            print(f"[Zoom API] Creating {session_type}: {topic}")
            print(f"[Zoom API] Start Time: {start_time}")
            print(f"[Zoom API] Duration: {duration} minutes")
            
            token = self.get_access_token()
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Zoom API v2 webinar/meeting settings
            # Only include settings that are explicitly supported
            webinar_settings = {
                'host_video': True,
                'participant_video': True,
                'join_before_host': False,
                'mute_upon_entry': False,
            }
            
            if settings_dict:
                webinar_settings.update(settings_dict)
            
            # Build minimal payload that matches Zoom API requirements
            # Type 2 = Scheduled webinar/meeting
            payload = {
                'topic': str(topic)[:300],  # Max 300 chars
                'type': 2,
                'start_time': start_time,  # ISO 8601: 2024-02-10T10:00:00
                'duration': int(duration),
                'timezone': 'Asia/Kolkata',
                'settings': webinar_settings
            }
            
            print(f"[Zoom API] Sending payload: {payload}")
            
            # Route to correct endpoint based on session_type
            if session_type.lower() == 'meeting':
                endpoint = f"{self.API_BASE_URL}/users/me/meetings"
                print(f"[Zoom API] Using MEETING endpoint: {endpoint}")
            else:
                endpoint = f"{self.API_BASE_URL}/users/me/webinars"
                print(f"[Zoom API] Using WEBINAR endpoint: {endpoint}")
            
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            # Log all response details
            print(f"[Zoom API] Response status: {response.status_code}")
            print(f"[Zoom API] Response headers: {response.headers}")
            print(f"[Zoom API] Response body: {response.text}")
            
            if response.status_code != 201:
                try:
                    error_data = response.json()
                    print(f"[Zoom API] ❌ Error response: {error_data}")
                    error_msg = error_data.get('message', 'Unknown error')
                    details = error_data.get('details', [])
                    if details:
                        error_msg += f" - {details[0].get('message', '')}"
                    raise Exception(f"Zoom API Error: {error_msg}")
                except ValueError:
                    raise Exception(f"Zoom API Error: {response.text}")
            
            meeting_data = response.json()
            print(f"[Zoom API] ✓ {session_type.capitalize()} created successfully")
            print(f"[Zoom API] ID: {meeting_data.get('id', 'N/A')}")
            print(f"[Zoom API] Passcode: {meeting_data.get('password', 'N/A')}")
            
            return {
                'meeting_id': str(meeting_data.get('id', '')),
                'join_url': meeting_data.get('join_url', ''),
                'passcode': meeting_data.get('password', ''),
                'start_time': meeting_data.get('start_time', ''),
                'duration': meeting_data.get('duration', 0),
                'session_type': session_type,
            }
            
        except requests.exceptions.Timeout:
            error_msg = "Timeout: Zoom API request took too long"
            print(f"[Zoom API] ❌ {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            print(f"[Zoom API] ❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"[Zoom API] ❌ Error creating {session_type}: {str(e)}")
            raise


class ZoomSignatureAPIView(APIView):
    """
    Generate JWT signature for Zoom Web SDK (webinars and meetings)
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

            print(f"🟢 Generating signature for webinar/meeting {meeting_number}, role {role}")

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


class CreateZoomMeetingAPIView(APIView):
    """
    Create a Zoom webinar or meeting via OAuth API
    """
    def post(self, request):
        try:
            print("🔵 [CreateZoomMeetingAPIView] Request received")
            
            topic = request.data.get("topic", "").strip()
            start_time = request.data.get("start_time", "").strip()
            duration = int(request.data.get("duration", 60))
            session_type = request.data.get("session_type", "webinar").strip().lower()
            
            print(f"[CreateZoomMeetingAPIView] Topic: {topic}")
            print(f"[CreateZoomMeetingAPIView] Start Time: {start_time}")
            print(f"[CreateZoomMeetingAPIView] Duration: {duration}")
            print(f"[CreateZoomMeetingAPIView] Session Type: {session_type}")
            
            if not topic or not start_time:
                return Response(
                    {"error": "Topic and start_time are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate session_type
            if session_type not in ['webinar', 'meeting']:
                return Response(
                    {"error": "session_type must be 'webinar' or 'meeting'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate start_time format
            from datetime import datetime
            try:
                # Try to parse the datetime
                meeting_datetime = datetime.fromisoformat(start_time)
                print(f"[CreateZoomMeetingAPIView] Parsed datetime: {meeting_datetime}")
                
                # Check if it's in the future
                if meeting_datetime <= datetime.now():
                    return Response(
                        {"error": "Meeting start time must be in the future"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError as e:
                print(f"[CreateZoomMeetingAPIView] Invalid datetime format: {str(e)}")
                return Response(
                    {"error": f"Invalid datetime format. Use ISO format (e.g., 2024-02-10T10:00:00): {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create webinar/meeting using OAuth
            oauth_manager = ZoomOAuthManager()
            meeting_data = oauth_manager.create_meeting(
                topic=topic,
                start_time=start_time,
                duration=duration,
                session_type=session_type
            )
            
            return Response({
                "success": True,
                "data": meeting_data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"❌ Error in CreateZoomMeetingAPIView: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefreshZoomTokenAPIView(APIView):
    """
    Manually refresh Zoom OAuth token
    Use this after adding new scopes to your Zoom app
    """
    def post(self, request):
        try:
            print("🔄 [RefreshZoomTokenAPIView] Token refresh requested")
            
            oauth_manager = ZoomOAuthManager()
            new_token = oauth_manager.refresh_token()
            
            return Response({
                "success": True,
                "message": "Zoom OAuth token refreshed successfully with new scopes",
                "token_expires_in": oauth_manager.token_expiry - time.time()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error refreshing token: {str(e)}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )