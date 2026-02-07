# Zoom SDK Flutter Integration Workflow

## Overview
This document outlines the complete workflow for integrating Zoom SDK in your Flutter application with your Django backend.

---

## 1. Backend Setup (COMPLETED ✓)

### Environment Variables Required
Add these to your `.env` file:
```env
ZOOM_SDK_KEY=your_zoom_sdk_key_here
ZOOM_SDK_SECRET=your_zoom_sdk_secret_here
```

**Where to get these:**
- Login to [Zoom App Marketplace](https://marketplace.zoom.us/)
- Create a new SDK app
- Navigate to "App Credentials" section
- Copy your SDK Key and SDK Secret

### Backend Endpoints Setup

#### 1. Get Active Live Sessions
**Endpoint:** `GET /api/auth/live-sessions/`
**Authentication:** No authentication required
**Response (200):**
```json
{
  "status": 200,
  "message": "Live sessions fetched successfully",
  "response": {
    "total_sessions": 2,
    "sessions": [
      {
        "id": 1,
        "title": "Python Crash Course - Live Q&A",
        "agenda": "Discussion about Python fundamentals and project structure",
        "thumbnail": "http://localhost:8000/media/live_sessions/thumbnails/session1.jpg",
        "meeting_number": "1234567890",
        "Passcode": "123456",
        "meeting_url": "https://zoom.us/...",
        "session_date": "2026-02-15",
        "session_time": "18:30:00",
        "session_time_ist": "06:30 PM",
        "session_datetime_ist": "15 Feb 2026, 06:30 PM IST",
        "is_active": true,
        "created_at": "2026-02-07T10:00:00Z"
      }
    ]
  }
}
```

#### 2. Get Specific Live Session Details
**Endpoint:** `GET /api/auth/live-sessions/<session_id>/`
**Authentication:** No authentication required
**Response (200):** [Same structure as single session above]

#### 3. Generate Zoom JWT Token ⭐
**Endpoint:** `POST /api/auth/zoom-token/`
**Authentication:** Required (Bearer token)
**Request Headers:**
```
Authorization: Bearer <user_access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "meeting_number": "1234567890",
  "session_id": 1,
  "user_display_name": "John Doe"
}
```

**Response (200):**
```json
{
  "status": 200,
  "message": "Zoom token generated successfully",
  "response": {
    "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600,
    "expires_at": "2026-02-07T11:07:12.345678Z",
    "meeting_number": "1234567890"
  }
}
```

**Error Responses:**

401 Unauthorized:
```json
{
  "status": 401,
  "message": "Unauthorized",
  "response": null
}
```

400 Bad Request:
```json
{
  "status": 400,
  "message": "Validation error",
  "response": {
    "meeting_number": ["Meeting not found"],
    "user_display_name": ["This field is required"]
  }
}
```

---

## 2. Flutter Integration Flow

### Complete User Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUTTER APP WORKFLOW                         │
└─────────────────────────────────────────────────────────────────┘

1. USER LAUNCHES APP
   ↓
2. USER LOGS IN
   └─→ POST /api/auth/user-login/
   └─→ Receives access_token & refresh_token
   ↓
3. FETCH ACTIVE LIVE SESSIONS
   └─→ GET /api/auth/live-sessions/
   └─→ Shows list of upcoming/active sessions
   ↓
4. USER SELECTS A SESSION TO JOIN
   └─→ Display session details
   ↓
5. REQUEST ZOOM TOKEN
   └─→ POST /api/auth/zoom-token/
       {
         "meeting_number": "from_live_sessions_api",
         "session_id": "optional",
         "user_display_name": "John Doe"
       }
   └─→ Receives JWT token with 1-hour expiry
   ↓
6. INITIALIZE ZOOM SDK IN FLUTTER
   └─→ Use JWT token from step 5
   └─→ Join meeting with meeting_number
   ↓
7. USER JOINS MEETING IN ZOOM
   └─→ Video/Audio conference active
   ↓
8. TRACK SESSION PROGRESS (Optional)
   └─→ Record watch time
   └─→ Update UserProgress model
   ↓
9. SESSION ENDS / USER LEAVES
   └─→ Token automatically expires (3600 seconds)
   └─→ New token required for next join
```

---

## 3. Flutter Implementation Steps

### Step 1: Install Zoom SDK Package
Add to `pubspec.yaml`:
```yaml
dependencies:
  zoom_sdk_flutter: ^2.8.0
  dio: ^5.3.1
  shared_preferences: ^2.2.0
```

### Step 2: Authentication Service
```dart
// lib/services/auth_service.dart
class AuthService {
  final String baseUrl = 'http://your-backend.com/api/auth';
  final dio = Dio();
  
  // Store tokens after login
  Future<void> login(String email, String password) async {
    final response = await dio.post(
      '$baseUrl/user-login/',
      data: {
        'email': email,
        'password': password,
      },
    );
    
    final accessToken = response.data['response']['tokens']['access'];
    final refreshToken = response.data['response']['tokens']['refresh'];
    
    // Store tokens securely
    await saveTokens(accessToken, refreshToken);
  }
}
```

### Step 3: Live Sessions Service
```dart
// lib/services/live_session_service.dart
class LiveSessionService {
  final String baseUrl = 'http://your-backend.com/api/auth';
  final dio = Dio();
  
  Future<List<LiveSession>> getActiveSessions() async {
    final response = await dio.get(
      '$baseUrl/live-sessions/',
    );
    
    List<LiveSession> sessions = [];
    final sessionList = response.data['response']['sessions'];
    
    for (var session in sessionList) {
      sessions.add(LiveSession.fromJson(session));
    }
    
    return sessions;
  }
}

class LiveSession {
  final int id;
  final String title;
  final String agenda;
  final String meetingNumber;
  final String sessionDateTimeIst;
  final bool isActive;
  
  factory LiveSession.fromJson(Map<String, dynamic> json) {
    return LiveSession(
      id: json['id'],
      title: json['title'],
      agenda: json['agenda'],
      meetingNumber: json['meeting_number'],
      sessionDateTimeIst: json['session_datetime_ist'],
      isActive: json['is_active'],
    );
  }
}
```

### Step 4: Zoom Token Service ⭐
```dart
// lib/services/zoom_token_service.dart
class ZoomTokenService {
  final String baseUrl = 'http://your-backend.com/api/auth';
  final dio = Dio();
  
  Future<ZoomTokenResponse> generateZoomToken({
    required String meetingNumber,
    required String userDisplayName,
    int? sessionId,
  }) async {
    try {
      final accessToken = await getAccessToken(); // From SharedPreferences
      
      final response = await dio.post(
        '$baseUrl/zoom-token/',
        options: Options(
          headers: {
            'Authorization': 'Bearer $accessToken',
            'Content-Type': 'application/json',
          },
        ),
        data: {
          'meeting_number': meetingNumber,
          'user_display_name': userDisplayName,
          if (sessionId != null) 'session_id': sessionId,
        },
      );
      
      return ZoomTokenResponse.fromJson(response.data['response']);
    } on DioException catch (e) {
      throw ZoomTokenException(e.response?.data['message'] ?? 'Failed to generate token');
    }
  }
}

class ZoomTokenResponse {
  final String jwtToken;
  final int expiresIn;
  final String expiresAt;
  final String meetingNumber;
  
  ZoomTokenResponse({
    required this.jwtToken,
    required this.expiresIn,
    required this.expiresAt,
    required this.meetingNumber,
  });
  
  factory ZoomTokenResponse.fromJson(Map<String, dynamic> json) {
    return ZoomTokenResponse(
      jwtToken: json['jwt_token'],
      expiresIn: json['expires_in'],
      expiresAt: json['expires_at'],
      meetingNumber: json['meeting_number'],
    );
  }
}
```

### Step 5: Zoom Meeting UI Integration
```dart
// lib/screens/live_session_detail_screen.dart
class LiveSessionDetailScreen extends StatelessWidget {
  final LiveSession session;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(session.title)),
      body: Column(
        children: [
          // Session details
          ListTile(
            title: Text('Date & Time'),
            subtitle: Text(session.sessionDateTimeIst),
          ),
          ListTile(
            title: Text('Status'),
            subtitle: Text(
              session.isActive ? '🔴 LIVE' : '⏳ Upcoming',
              style: TextStyle(
                color: session.isActive ? Colors.red : Colors.orange,
              ),
            ),
          ),
          
          // Join Meeting Button
          ElevatedButton(
            onPressed: session.isActive 
              ? () => _joinZoomMeeting(context, session)
              : null,
            child: Text('Join Meeting'),
          ),
        ],
      ),
    );
  }
  
  void _joinZoomMeeting(BuildContext context, LiveSession session) async {
    try {
      // Show loading
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => Center(child: CircularProgressIndicator()),
      );
      
      // Get current user name
      final userName = await getCurrentUserName();
      
      // Generate zoom token from backend
      final zoomService = ZoomTokenService();
      final tokenResponse = await zoomService.generateZoomToken(
        meetingNumber: session.meetingNumber,
        userDisplayName: userName,
        sessionId: session.id,
      );
      
      // Close loading dialog
      Navigator.pop(context);
      
      // Join zoom meeting
      await _initializeAndJoinZoom(
        tokenResponse.jwtToken,
        tokenResponse.meetingNumber,
      );
      
    } catch (e) {
      Navigator.pop(context); // Close loading if still open
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${e.toString()}')),
      );
    }
  }
  
  Future<void> _initializeAndJoinZoom(String jwtToken, String meetingNumber) async {
    try {
      // Initialize Zoom SDK
      ZoomSDK zoomSDK = ZoomSDK();
      
      var isMeetingSecure = false; // Check if passcode required
      
      // Join meeting
      var joinMeetingResult = await zoomSDK.joinMeeting(
        meetingNumber: meetingNumber,
        userName: 'User',
        zoomAccessToken: jwtToken,
        userId: '', // Not required for SDK
        isSecure: isMeetingSecure,
      );
      
    } catch (e) {
      print('Error joining meeting: $e');
      rethrow;
    }
  }
}
```

---

## 4. Key Security Considerations

### ✅ Best Practices

1. **Token Expiration**
   - JWT tokens expire in 1 hour (3600 seconds)
   - Generate a new token for each meeting join
   - Never reuse expired tokens

2. **Authentication**
   - Always include Bearer token in Authorization header
   - Store tokens securely using flutter_secure_storage
   - Implement token refresh logic

3. **Input Validation**
   - Meeting number must be digits only
   - User display name limited to 100 characters
   - Session ID is optional but should reference valid sessions

4. **Error Handling**
   - Handle 401 (Unauthorized) - Ask user to re-login
   - Handle 400 (Bad Request) - Show validation errors
   - Handle 500 (Server Error) - Show generic error message

### ❌ Don't Do

- ❌ Store tokens in SharedPreferences without encryption
- ❌ Hardcode Zoom SDK credentials
- ❌ Pass meeting number directly from client without backend validation
- ❌ Cache JWT tokens (generate fresh for each meeting)

---

## 5. Testing Checklist

- [ ] Create test user and login successfully
- [ ] Verify access token received from login endpoint
- [ ] Fetch live sessions list (empty or populated)
- [ ] Get specific session details
- [ ] Generate zoom token with valid meeting number
- [ ] Generate zoom token with invalid meeting number (should fail)
- [ ] Verify token expiration logic (3600 seconds)
- [ ] Join Zoom meeting with valid token
- [ ] Attempt to join with invalid token (should fail)
- [ ] Test token refresh after 1 hour
- [ ] Verify meeting end updates user progress

---

## 6. API Response Summary

### Status Codes Reference

| Code | Scenario |
|------|----------|
| 200 | Request successful |
| 201 | Resource created |
| 400 | Validation error (invalid meeting number, name, etc.) |
| 401 | Unauthorized (no token or invalid token) |
| 404 | Resource not found |
| 500 | Server error (missing Zoom credentials) |

---

## 7. Troubleshooting

### Issue: "Meeting not found"
**Solution:** Ensure the meeting_number in request matches exactly with the value from live-sessions API

### Issue: "Zoom SDK credentials not configured"
**Solution:** 
- Check `.env` file has `ZOOM_SDK_KEY` and `ZOOM_SDK_SECRET`
- Restart Django server after adding env variables
- Verify credentials are valid from Zoom App Marketplace

### Issue: Token expires midway through meeting
**Solution:** This is expected behavior. For long meetings, implement token refresh. However, typically meetings run < 1 hour.

### Issue: "User not authenticated"
**Solution:** 
- Include `Authorization: Bearer <token>` header
- Verify access token is not expired
- Login again to get fresh token

---

## 8. Frontend Flow Diagram

```
┌─────────────────┐
│  Login Screen   │
└────────┬────────┘
         │ Email + Password
         ↓
┌─────────────────────────┐
│ POST /user-login/       │
│ Returns: access_token   │
└────────┬────────────────┘
         │ Store token locally
         ↓
┌─────────────────────────────┐
│ Live Sessions List Screen   │
└────────┬────────────────────┘
         │ GET /live-sessions/
         │ Display upcoming/active sessions
         ↓
┌──────────────────────────────┐
│ Session Detail / Join Button │
└────────┬─────────────────────┘
         │ User clicks "Join Meeting"
         ↓
┌────────────────────────────────────┐
│ POST /zoom-token/                  │
│ Send: meeting_number, user_name    │
│ Receive: jwt_token (expires 3600s) │
└────────┬───────────────────────────┘
         │ Use JWT token
         ↓
┌──────────────────────────────┐
│ Initialize Zoom SDK          │
│ Join Meeting                 │
└──────────────────────────────┘
         │
         ↓
┌──────────────────────────────┐
│ Video Conference Active      │
└──────────────────────────────┘
```

---

## 9. Environment Setup for Backend

### Required Packages (Already Installed)
- ✅ PyJWT==2.10.1
- ✅ djangorestframework
- ✅ python-decouple

### Environment Variables Template (.env file)
```env
# Database
DATABASE_URL=...

# Zoom Credentials
ZOOM_SDK_KEY=your_sdk_key_from_zoom_marketplace
ZOOM_SDK_SECRET=your_sdk_secret_from_zoom_marketplace

# Other settings
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

---

## 10. Zoom App Marketplace Setup

1. **Create SDK App:**
   - Go to https://marketplace.zoom.us/develop/create
   - Choose "SDK" as app type
   - Select "Web" or "Mobile SDK"

2. **Configure App:**
   - Set Verified name
   - Copy SDK Key and Secret (use in `.env`)
   - Enable features: Video Calls, Screen Share

3. **Set Restrictions:**
   - Add your domain/IP allowlist if needed
   - Set redirect URLs for OAuth (if applicable)

---

## Summary of Changes Made

✅ **Backend Implementation:**
- Added `ZoomTokenRequestSerializer` in [auth_app/serializers.py](auth_app/serializers.py)
- Created `ZoomTokenGeneratorAPIView` in [auth_app/views.py](auth_app/views.py)
- Added route `POST /api/auth/zoom-token/` in [auth_app/urls.py](auth_app/urls.py)
- JWT token generation using HS256 algorithm
- 1-hour token expiration with ISO 8601 timestamp

✅ **Exported Endpoints:**
1. `GET /api/auth/live-sessions/` - List all active sessions
2. `GET /api/auth/live-sessions/<id>/` - Get session details
3. `POST /api/auth/zoom-token/` - Generate Zoom JWT token

Ready for Flutter integration! 🚀
