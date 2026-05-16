/**
 * API Client for Research Agent Backend
 * Handles auth, research, sessions, and streaming endpoints
 */

let API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Ensure absolute URL
if (API_BASE && !API_BASE.startsWith('http')) {
  API_BASE = `https://${API_BASE}`;
}

// ── Token helpers ──────────────────────────────
function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

function setToken(token) {
  localStorage.setItem('access_token', token);
}

function clearToken() {
  localStorage.removeItem('access_token');
}

// ── Base fetch wrapper ─────────────────────────
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:logout', { 
        detail: { message: 'Session expired. Please log in again.' } 
      }));
    }
    throw new ApiError('Session expired. Please log in again.', 401);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Request failed (${res.status})`, res.status);
  }

  return res.json();
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

// ═══════════════════════════════════════════════
//  AUTH ENDPOINTS
// ═══════════════════════════════════════════════

export async function register(username, email, password) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  });
}

export async function login(username, password) {
  const data = await apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function refreshToken(token) {
  const data = await apiFetch('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
  setToken(data.access_token);
  return data;
}

export async function getMe() {
  return apiFetch('/auth/me');
}

export async function logout() {
  try {
    await apiFetch('/auth/logout', { method: 'POST' });
  } catch (err) {
    // If logout fails (e.g. token already expired), just log it and proceed
    console.warn('Server-side logout failed:', err);
  } finally {
    clearToken();
  }
}

// ═══════════════════════════════════════════════
//  RESEARCH ENDPOINTS
// ═══════════════════════════════════════════════

export async function startResearch(query, webSearchEnabled = true, maxIterations = 5) {
  return apiFetch('/research/start', {
    method: 'POST',
    body: JSON.stringify({
      query,
      web_search_enabled: webSearchEnabled,
      max_iterations: maxIterations
    }),
  });
}

export async function getResearchSession(sessionId) {
  return apiFetch(`/research/${sessionId}`);
}

/**
 * Stream research execution via NDJSON.
 * @param {string} sessionId
 * @param {function} onStep - Called with each agent step {type, node, label, iteration}
 * @param {function} onResult - Called with final result {answer, messages, quality_score, ...}
 * @param {function} onError - Called on error
 * @returns {AbortController} controller to abort the stream
 */
export function streamResearch(sessionId, query, webSearchEnabled, onStep, onResult, onError) {
  const controller = new AbortController();
  const token = getToken();

  const options = {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    signal: controller.signal,
  };

  if (query) {
    options.body = JSON.stringify({
      query,
      web_search_enabled: webSearchEnabled,
      max_iterations: 5
    });
  }

  fetch(`${API_BASE}/research/${sessionId}/stream`, options)
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Stream failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          try {
            const data = JSON.parse(trimmed);
            if (data.type === 'agent') {
              onStep(data);
            } else if (data.type === 'result') {
              onResult(data);
            } else if (data.type === 'error') {
              onError(data.detail || 'Unknown error');
            }
          } catch {
            // skip malformed lines
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err.message);
      }
    });

  return controller;
}

export async function interruptResearch(sessionId) {
  return apiFetch(`/research/${sessionId}/interrupt`, { method: 'POST' });
}

// ═══════════════════════════════════════════════
//  SESSION ENDPOINTS
// ═══════════════════════════════════════════════

export async function getUserSessions(userId, skip = 0, limit = 50) {
  return apiFetch(`/sessions/${userId}?skip=${skip}&limit=${limit}`);
}

export async function getSessionHistory(sessionId) {
  return apiFetch(`/sessions/${sessionId}/history`);
}

export async function deleteSession(sessionId) {
  return apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function getResearchLogs(sessionId) {
  return apiFetch(`/research/${sessionId}/logs`);
}

// ═══════════════════════════════════════════════
//  DOCUMENT ENDPOINTS
// ═══════════════════════════════════════════════

export async function uploadDocument(file) {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth:logout'));
    }
    throw new ApiError('Session expired. Please log in again.', 401);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Upload failed (${res.status})`, res.status);
  }

  return res.json();
}

export async function listDocuments() {
  return apiFetch('/documents');
}

export async function deleteDocument(documentId) {
  return apiFetch(`/documents/${documentId}`, { method: 'DELETE' });
}

// ═══════════════════════════════════════════════
//  SYSTEM ENDPOINTS
// ═══════════════════════════════════════════════

export async function healthCheck() {
  return apiFetch('/health');
}

export async function apiInfo() {
  return apiFetch('/api/info');
}

// Re-export helpers
export { getToken, clearToken, ApiError };
