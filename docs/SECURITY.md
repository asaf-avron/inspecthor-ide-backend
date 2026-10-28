# Security Policy

## API Authentication

### Overview

Inspecthor uses API key authentication to secure communication between the frontend and backend. This is a simple but effective approach for service-to-service authentication.

### Setup

#### Backend Configuration

1. Generate secure API keys:
```bash
# Generate a random API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Add to backend `.env`:
```bash
ALLOWED_API_KEYS=key1,key2,key3
```

3. The backend validates the `X-API-Key` header on all requests except `/api/health`.

#### Frontend Configuration

1. Add API key to frontend `.env.local`:
```bash
INSPECTHOR_API_KEY=key1
```

2. The API client automatically includes the key in request headers.

### Best Practices

- **Never commit API keys** to version control
- **Use different keys** for dev, staging, and production
- **Rotate keys regularly** (every 90 days recommended)
- **Use strong random keys** (32+ characters)
- **Limit key distribution** to only necessary services

## CORS Configuration

### Overview

Cross-Origin Resource Sharing (CORS) controls which frontend origins can access the backend API.

### Setup

#### Backend Configuration

Add allowed origins to backend `.env`:
```bash
# Development
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Production
CORS_ORIGINS=https://your-frontend.vercel.app,https://www.your-domain.com
```

### Best Practices

- **Never use `*` (wildcard)** in production
- **Use HTTPS** for all production origins
- **Whitelist specific domains** only
- **Include both www and non-www** if applicable
- **Update when deploying** new frontend instances

## Rate Limiting

### Overview

Rate limiting prevents API abuse by limiting requests per IP address.

### Setup

Configure in backend `.env`:
```bash
RATE_LIMIT_PER_MINUTE=60
```

### Best Practices

- **Set reasonable limits** based on expected usage
- **Monitor rate limit hits** in logs
- **Adjust limits** for production traffic patterns
- **Consider per-user limits** for future enhancements

## HTTPS/TLS

### Development

Local development uses HTTP for simplicity:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

### Production

**CRITICAL**: Production MUST use HTTPS for all traffic.

#### Recommended Platforms

**Frontend**:
- Vercel: Automatic HTTPS, free SSL certificates
- Netlify: Automatic HTTPS, free SSL certificates

**Backend**:
- Railway: Automatic HTTPS, free SSL certificates
- Render: Automatic HTTPS, free SSL certificates
- Google Cloud Run: Automatic HTTPS

#### Manual Setup

If self-hosting:
1. Obtain SSL certificate (Let's Encrypt recommended)
2. Configure reverse proxy (nginx, Caddy)
3. Enforce HTTPS redirects
4. Set HSTS headers

## Environment Variables

### Security Rules

1. **Never commit** `.env` files to git
2. **Use `.env.example`** for documentation
3. **Rotate secrets** regularly
4. **Use different values** for each environment
5. **Limit access** to production secrets

### Backend `.env`

```bash
# Required
GEMINI_API_KEY=<secret>
ALLOWED_API_KEYS=<secret>

# Optional (with defaults)
API_SECRET_KEY=<secret>
CORS_ORIGINS=http://localhost:3000
RATE_LIMIT_PER_MINUTE=60
```

### Frontend `.env.local`

```bash
# Required
NEXT_PUBLIC_API_URL=http://localhost:8000
INSPECTHOR_API_KEY=<secret>
```

### Deployment

**Vercel (Frontend)**:
```bash
vercel env add NEXT_PUBLIC_API_URL
vercel env add INSPECTHOR_API_KEY
```

**Railway (Backend)**:
```bash
railway variables set GEMINI_API_KEY=xxx
railway variables set ALLOWED_API_KEYS=xxx
railway variables set CORS_ORIGINS=https://your-frontend.vercel.app
```

## Request Logging

### Overview

All API requests are logged for security monitoring and debugging.

### Log Format

```
2026-01-25 14:00:00 - api.middleware - INFO - Request: POST /api/generate/spec from 192.168.1.1
2026-01-25 14:00:01 - api.middleware - INFO - Response: POST /api/generate/spec status=200 duration=1.234s
```

### Monitoring

- **Review logs regularly** for suspicious activity
- **Set up alerts** for high error rates
- **Monitor rate limit hits** by IP
- **Track API key usage** patterns

## Production Deployment Checklist

### Backend

- [ ] Generate strong API keys (32+ characters)
- [ ] Set `ALLOWED_API_KEYS` in production environment
- [ ] Configure `CORS_ORIGINS` with production frontend URL
- [ ] Set appropriate `RATE_LIMIT_PER_MINUTE`
- [ ] Enable HTTPS (automatic on Railway/Render)
- [ ] Set up log monitoring
- [ ] Test API key authentication
- [ ] Test CORS from production frontend
- [ ] Verify rate limiting works

### Frontend

- [ ] Set `NEXT_PUBLIC_API_URL` to production backend
- [ ] Set `INSPECTHOR_API_KEY` matching backend
- [ ] Enable HTTPS (automatic on Vercel)
- [ ] Test API calls to backend
- [ ] Verify no CORS errors in browser console
- [ ] Test error handling for auth failures

## Incident Response

### API Key Compromise

If an API key is compromised:

1. **Immediately remove** the key from `ALLOWED_API_KEYS`
2. **Generate new key** and distribute to legitimate services
3. **Review logs** for unauthorized usage
4. **Rotate all keys** as a precaution

### Security Vulnerability

If a security vulnerability is discovered:

1. **Assess impact** and severity
2. **Patch immediately** if critical
3. **Notify users** if data exposure occurred
4. **Document incident** and lessons learned

## Future Enhancements

### Planned Security Improvements

1. **OAuth 2.0**: User authentication via GitHub
2. **JWT tokens**: Stateless authentication
3. **Per-user rate limiting**: More granular control
4. **API key scopes**: Limit key permissions
5. **Audit logging**: Detailed security event tracking
6. **Intrusion detection**: Automated threat detection

## Contact

For security concerns or to report vulnerabilities, please contact:
- Email: [your-security-email]
- GitHub: [Create a private security advisory]
