---
name: oauth-patterns
description: >
  Reference patterns for OAuth 2.0 implementation, focused on Spotify's Authorization Code
  Flow with PKCE. Covers token management, refresh logic, session security, and Fernet encryption.
  Use when implementing or reviewing auth flows. Not an audit — provides patterns to follow.
---

# OAuth Patterns Skill

Reference implementation patterns for OAuth 2.0. Adapted for Spotify's API but applicable to any OAuth provider.

## When to Use

- Implementing OAuth login flow from scratch
- Reviewing existing auth implementation
- Fixing token refresh or session issues
- Adding new OAuth scopes
- Hardening auth security

## This Skill is a Reference

Unlike audit skills, `oauth-patterns` does NOT produce findings. It provides:
- Patterns to follow during implementation
- Checklists to verify against
- Code snippets to adapt

## Patterns

### 1. Authorization Code Flow with PKCE

```
User → /login → redirect to Spotify /authorize
  → user approves → callback with ?code=xxx
  → backend exchanges code for tokens
  → tokens encrypted with Fernet, stored in DB
  → session cookie set (httponly, secure, samesite)
```

**Key files in this project:**
- `backend/app/routers/auth.py` — login, callback, logout, refresh endpoints
- `backend/app/services/spotify_client.py` — token-aware API wrapper
- `backend/app/utils/token_manager.py` — Fernet encryption/decryption
- `backend/app/config.py` — OAuth config (client_id, secret, redirect_uri)

### 2. Token Refresh Pattern

```python
# In spotify_client.py — auto-refresh before API calls
async def _ensure_valid_token(self):
    if self._is_token_expired():
        new_tokens = await self._refresh_token()
        await self._save_encrypted_tokens(new_tokens)
```

**Rules:**
- Always check expiry BEFORE making API calls
- Refresh token has no expiry but can be revoked
- On InvalidToken (Fernet decryption fails) → raise SpotifyAuthError → 401

### 3. SpotifyAuthError Propagation

```python
# In every router that calls SpotifyClient:
try:
    result = await client.get_top_tracks(...)
except SpotifyAuthError:
    raise  # MUST re-raise before generic except
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(500)
```

**Rule:** NEVER catch SpotifyAuthError in a generic `except Exception`. Always re-raise it so the frontend gets a 401 and can redirect to login.

### 4. Session Security Checklist

- [ ] Session cookie: `httponly=True`, `secure=True` (in production), `samesite=Lax`
- [ ] Session secret: NOT the default value (warn at startup)
- [ ] Encryption salt: NOT the default value (warn at startup)
- [ ] Tokens encrypted at rest with Fernet (never stored plaintext)
- [ ] PKCE code verifier: generated per-session, stored in session
- [ ] State parameter: validated on callback to prevent CSRF
- [ ] Scopes: minimal required set (user-read-recently-played, user-top-read, etc.)

### 5. Rate Limiting

- Spotify API: 30 requests/second per app
- Use `asyncio.Semaphore(10)` for parallel calls
- Implement exponential backoff on 429 responses
- Rate limiter on auth endpoints: prevent brute force

## Verification Checklist

After implementing or modifying auth:
1. Fresh login works (clear cookies → /login → callback → dashboard)
2. Token refresh works (wait for expiry → next API call succeeds)
3. Logout clears session + redirects to /login
4. Invalid/expired token → 401 → frontend redirect
5. Fernet InvalidToken → SpotifyAuthError → 401 (not 500)
6. No secrets in logs, error messages, or API responses
