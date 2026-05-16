# API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication

Most endpoints require JWT authentication. Include the token in the `Authorization` header:
```
Authorization: Bearer {access_token}
```

---

## Authentication Endpoints

### 1. Register User
**POST** `/auth/register`

Create a new user account.

**Request Body:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password_at_least_8_chars"
}
```

**Response (201 Created):**
```json
{
  "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "username": "john_doe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2026-05-14T10:30:00",
  "updated_at": "2026-05-14T10:30:00",
  "last_login": null
}
```

**Errors:**
- 400 Bad Request: Username/email already exists or password too short
- 400 Bad Request: Invalid email format

---

### 2. Login
**POST** `/auth/login`

Authenticate user and get JWT token.

**Request Body:**
```json
{
  "username": "john_doe",
  "password": "secure_password_at_least_8_chars"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

**Errors:**
- 401 Unauthorized: Invalid username or password
- 403 Forbidden: User account is inactive

---

### 3. Refresh Token
**POST** `/auth/refresh`

Refresh an expired JWT token.

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

---

### 4. Get Current User
**GET** `/auth/me`

Get information about the authenticated user.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "username": "john_doe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2026-05-14T10:30:00",
  "updated_at": "2026-05-14T10:30:00",
  "last_login": "2026-05-14T10:35:00"
}
```

---

### 5. Logout
**POST** `/auth/logout`

Logout and revoke all tokens.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

---

## Research Endpoints

### 1. Start Research Session
**POST** `/research/start`

Start a new research session.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "query": "What are the latest AI trends in 2026?",
  "max_iterations": 5
}
```

**Response (200 OK):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "created_at": "2026-05-14T10:30:00"
}
```

**Errors:**
- 401 Unauthorized: Invalid or missing JWT token
- 400 Bad Request: Query is empty

---

### 2. Get Research Session
**GET** `/research/{session_id}`

Get details of a research session.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "What are the latest AI trends in 2026?",
  "final_answer": "Based on recent research, key AI trends include...",
  "quality_score": 0.85,
  "status": "completed",
  "created_at": "2026-05-14T10:30:00",
  "updated_at": "2026-05-14T10:35:00"
}
```

**Errors:**
- 404 Not Found: Session not found
- 403 Forbidden: User doesn't own this session

---

### 3. Stream Research Execution
**POST** `/research/{session_id}/stream`

Stream research progress in real-time using Server-Sent Events.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK - Stream):**

The response is a stream of NDJSON (newline-delimited JSON). Each line is a separate JSON object:

**Agent Update:**
```json
{
  "type": "agent",
  "node": "researcher",
  "label": "Researcher",
  "iteration": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Final Result:**
```json
{
  "type": "result",
  "answer": "Based on research, key AI trends include...",
  "messages": ["Supervisor: routing to researcher", "Researcher: searching web..."],
  "quality_score": 0.85,
  "interrupted": false,
  "error": null,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Event:**
```json
{
  "type": "error",
  "detail": "API error occurred",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### 4. Interrupt Research
**POST** `/research/{session_id}/interrupt`

Stop a running research session.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "Interrupt signal sent"
}
```

**Errors:**
- 404 Not Found: Session not found
- 400 Bad Request: Session is not currently active
- 403 Forbidden: User doesn't own this session

---

## Session Management Endpoints

### 1. List User Sessions
**GET** `/sessions/{user_id}`

Get all research sessions for a user (paginated).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `skip`: Number of sessions to skip (default: 0)
- `limit`: Maximum sessions to return (default: 50)

**Response (200 OK):**
```json
{
  "total": 25,
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "query": "What are the latest AI trends?",
      "final_answer": "Based on research...",
      "quality_score": 0.85,
      "status": "completed",
      "created_at": "2026-05-14T10:30:00",
      "updated_at": "2026-05-14T10:35:00"
    },
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440001",
      "query": "Explain blockchain technology",
      "final_answer": "Blockchain is a distributed ledger...",
      "quality_score": 0.92,
      "status": "completed",
      "created_at": "2026-05-13T15:20:00",
      "updated_at": "2026-05-13T15:25:00"
    }
  ]
}
```

**Errors:**
- 403 Forbidden: User can only access own sessions

---

### 2. Get Session History
**GET** `/sessions/{session_id}/history`

Get full chat history for a session.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "What are the latest AI trends?",
  "messages": [
    {
      "type": "user",
      "content": "What are the latest AI trends?",
      "timestamp": "2026-05-14T10:30:00"
    },
    {
      "type": "assistant",
      "content": "I'll research the latest AI trends...",
      "timestamp": "2026-05-14T10:30:05"
    },
    {
      "type": "assistant",
      "content": "Based on research, key trends include...",
      "timestamp": "2026-05-14T10:35:00"
    }
  ]
}
```

**Errors:**
- 404 Not Found: Session not found
- 403 Forbidden: User doesn't own this session

---

### 3. Delete/Archive Session
**DELETE** `/sessions/{session_id}`

Archive a session (soft delete - data is retained).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200 OK):**
```json
{
  "message": "Session archived"
}
```

**Errors:**
- 404 Not Found: Session not found
- 403 Forbidden: User doesn't own this session
- 500 Internal Server Error: Failed to delete

---

## System Endpoints

### 1. Health Check
**GET** `/health`

Check if the API is running and healthy.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-05-14T10:30:00",
  "version": "1.0.0"
}
```

---

### 2. API Information
**GET** `/api/info`

Get information about the API and available endpoints.

**Response (200 OK):**
```json
{
  "version": "1.0.0",
  "status": "healthy",
  "timestamp": "2026-05-14T10:30:00",
  "endpoints": {
    "authentication": [
      "POST /auth/register",
      "POST /auth/login",
      "POST /auth/refresh",
      "GET /auth/me",
      "POST /auth/logout"
    ],
    "research": [
      "POST /research/start",
      "GET /research/{session_id}",
      "POST /research/{session_id}/stream",
      "POST /research/{session_id}/interrupt"
    ],
    "sessions": [
      "GET /sessions/{user_id}",
      "GET /sessions/{session_id}/history",
      "DELETE /sessions/{session_id}"
    ],
    "health": [
      "GET /health",
      "GET /api/info"
    ]
  },
  "models": [
    "gpt-4o-mini",
    "gemini-2.5-pro"
  ]
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes
- **200 OK**: Request succeeded
- **201 Created**: Resource created successfully
- **202 Accepted**: Request accepted for async processing
- **400 Bad Request**: Invalid input or request format
- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: User doesn't have permission
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

---

## Usage Examples

### Complete Workflow Example

#### 1. Register a new user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "SecurePassword123"
  }'
```

#### 2. Login and get token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "SecurePassword123"
  }'
```

Save the `access_token` from the response.

#### 3. Start research session
```bash
curl -X POST http://localhost:8000/research/start \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is quantum computing?",
    "max_iterations": 5
  }'
```

Save the `session_id` from the response.

#### 4. Stream research progress
```bash
curl -X POST http://localhost:8000/research/{session_id}/stream \
  -H "Authorization: Bearer {access_token}"
```

#### 5. Get session results
```bash
curl -X GET http://localhost:8000/research/{session_id} \
  -H "Authorization: Bearer {access_token}"
```

#### 6. List all user sessions
```bash
curl -X GET "http://localhost:8000/sessions/{user_id}" \
  -H "Authorization: Bearer {access_token}"
```

#### 7. Get chat history
```bash
curl -X GET http://localhost:8000/sessions/{session_id}/history \
  -H "Authorization: Bearer {access_token}"
```

#### 8. Logout
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer {access_token}"
```

---

## Rate Limiting

Currently, there is no rate limiting implemented. Production deployments should add rate limiting to prevent abuse.

## CORS

CORS is enabled for all origins. In production, restrict this to trusted domains only.

## Future Enhancements

- [ ] OpenAPI/Swagger UI at `/docs`
- [ ] WebSocket support for real-time updates
- [ ] Rate limiting and API quotas
- [ ] API key authentication for service-to-service calls
- [ ] Webhook support for async notifications
- [ ] GraphQL API support
