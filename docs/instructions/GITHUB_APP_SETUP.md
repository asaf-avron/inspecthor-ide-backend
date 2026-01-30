# InSpecThor GitHub App Setup

## Overview

InSpecThor requires a GitHub App for:
- Webhooks for repository events (push, pull_request)
- Check Runs API for PR verification status
- Installation-level permissions (not user-level)
- Bot user for automated comments

## Step 1: Create GitHub App

1. Go to https://github.com/settings/apps/new (personal) or `https://github.com/organizations/{org}/settings/apps/new` (org)

2. Fill in the form:

### Basic Information
- **GitHub App name:** InSpecThor
- **Description:** Formal verification for your codebase - proof-driven development with Dafny
- **Homepage URL:** https://inspecthor.dev
- **Callback URL:** https://api.inspecthor.dev/github/callback
- **Setup URL:** https://inspecthor.dev/setup (optional)
- **Webhook URL:** https://api.inspecthor.dev/github/webhooks
- **Webhook secret:** Generate a strong secret and save to `.env` as `GITHUB_WEBHOOK_SECRET`

### Permissions

#### Repository permissions:
- **Contents:** Read (to fetch files)
- **Pull requests:** Read & write (to comment and update status)
- **Checks:** Read & write (to create check runs)
- **Metadata:** Read (basic repo info - automatically included)

#### Subscribe to events:
- [x] Push
- [x] Pull request
- [x] Installation
- [x] Installation repositories

### Where can this GitHub App be installed?
- Select: **Any account**

## Step 2: Generate Private Key

After creating the app:

1. Scroll to "Private keys" section
2. Click "Generate a private key"
3. Save the downloaded `.pem` file securely
4. Add to `.env`:
   ```
   GITHUB_APP_ID=123456
   GITHUB_APP_PRIVATE_KEY_PATH=/path/to/private-key.pem
   ```

   Or inline (for production):
   ```
   GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
   ```

## Step 3: Environment Variables

Add to `api/.env`:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_WEBHOOK_SECRET=your-webhook-secret-here
GITHUB_CLIENT_ID=Iv1.your-client-id
GITHUB_CLIENT_SECRET=your-client-secret
```

## Step 4: Install App

1. Go to app settings page
2. Click "Install App"
3. Select account/organization
4. Choose repositories (All or Select)
5. Click "Install"

## Step 5: Test Webhook

```bash
# Send test webhook
curl -X POST https://api.inspecthor.dev/github/webhooks \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d '{"zen": "Design for failure."}'
```

## Development Setup (Localhost)

For local development, you need to expose your localhost to the internet so GitHub can send webhooks. We recommend **Smee.io** (simplest) or **ngrok** (alternative).

### Option 1: Using Smee.io (Recommended - Simplest)

Smee.io is a free webhook proxy service specifically designed for GitHub webhooks. It's the easiest option.

#### Step 1: Create Smee Channel

1. Go to https://smee.io/
2. Click **"Start a new channel"**
3. Copy the channel URL (e.g., `https://smee.io/ABC123xyz`)

#### Step 2: Install smee-client

```bash
npm install -g smee-client
```

#### Step 3: Start Smee Forwarding

```bash
smee --url https://smee.io/YOUR_CHANNEL_ID --target http://localhost:8000/api/github/webhooks
```

Keep this terminal running!

#### Step 4: Create GitHub App

Use the Smee URL in GitHub App settings:

- **Webhook URL:** `https://smee.io/YOUR_CHANNEL_ID`
- **Callback URL:** `http://localhost:8000/api/auth/github/callback`

**Advantages of Smee:**
- ✅ Channel URL never changes (unlike free ngrok)
- ✅ No signup/authtoken needed
- ✅ Specifically designed for webhooks
- ✅ Free forever

### Option 2: Using ngrok (Alternative)

#### Step 1: Install ngrok

**Windows:**
```powershell
# Using Chocolatey
choco install ngrok

# Or download from https://ngrok.com/download
```

**macOS:**
```bash
brew install ngrok/ngrok/ngrok
```

**Linux:**
```bash
# Download from https://ngrok.com/download
# Or use snap
snap install ngrok
```

#### Step 2: Sign up and get auth token

1. Go to https://dashboard.ngrok.com/signup
2. Sign up for free account
3. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
4. Configure ngrok:
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### Step 3: Start ngrok tunnel

```bash
# Expose localhost:8000 (your backend API)
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123-def456.ngrok-free.app -> http://localhost:8000
```

**Copy the HTTPS URL** (e.g., `https://abc123-def456.ngrok-free.app`)

#### Step 4: Create GitHub App with Localhost URLs

1. Go to https://github.com/settings/apps/new

2. Fill in the form with **ngrok URLs**:

**Basic Information:**
- **GitHub App name:** InSpecThor (Local Dev)
- **Description:** Formal verification for your codebase - proof-driven development with Dafny (Local Development)
- **Homepage URL:** `https://abc123-def456.ngrok-free.app` (your ngrok URL)
- **Callback URL:** `https://abc123-def456.ngrok-free.app/api/auth/github/callback`
- **Setup URL:** (leave empty)
- **Webhook URL:** `https://abc123-def456.ngrok-free.app/api/github/webhooks`
- **Webhook secret:** Generate a strong secret (save this!)

**Permissions:** (same as production - see Step 1 above)

**Subscribe to events:**
- [x] Push
- [x] Pull request
- [x] Installation
- [x] Installation repositories

#### Step 5: Configure Environment Variables

Add to your `api/.env` file:

```bash
# GitHub App Configuration (Localhost)
GITHUB_APP_ID=123456  # From GitHub App settings page
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_WEBHOOK_SECRET=your-webhook-secret-from-step-4
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxxx  # From GitHub App settings page
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxx  # Generate in GitHub App settings

# Frontend OAuth callback (for user login)
GITHUB_OAUTH_REDIRECT_URI=http://localhost:3000/auth/github/callback
```

#### Step 6: Start Your Backend

```bash
cd api
uvicorn main:app --reload --port 8000
```

#### Step 7: Test Webhook Delivery

1. Go to your GitHub App settings: `https://github.com/settings/apps/YOUR_APP_NAME`
2. Click "Advanced" → "Recent Deliveries"
3. You should see webhook deliveries coming through

### Option 2: Using Cloudflare Tunnel (Alternative)

If you prefer Cloudflare Tunnel:

```bash
# Install cloudflared
# Windows: choco install cloudflared
# macOS: brew install cloudflared
# Linux: Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

Use the provided URL in GitHub App settings (same as ngrok).

### Important Notes for Localhost Development

1. **ngrok URL changes**: Free ngrok URLs change each time you restart. You'll need to update the GitHub App webhook URL each time.

2. **ngrok persistent URL** (Optional): For $5/month, you can get a static domain that doesn't change.

3. **Keep ngrok running**: The tunnel must stay active for webhooks to work. Consider running it in a separate terminal or as a background service.

4. **Webhook secret**: Generate a strong random secret and save it securely. Use it in both GitHub App settings and your `.env` file.

5. **Testing**: After setup, create a test repository and push a commit to verify webhooks are received.

### Quick Test Script

```bash
# Test webhook endpoint (from your local machine)
curl -X POST http://localhost:8000/api/github/webhooks \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "Design for failure."}'
```

If successful, you should see a response from your backend.

## Security Notes

1. **Never commit private key** - Add `*.pem` to `.gitignore`
2. **Rotate webhook secret** - If leaked, generate new secret
3. **Validate webhook signatures** - Always verify `X-Hub-Signature-256`
4. **Use installation tokens** - Short-lived, scoped tokens for API calls
5. **Audit logs** - Monitor app activity in GitHub settings

## Troubleshooting

### Webhook not received
- Check webhook URL is publicly accessible
- Verify webhook secret matches
- Check GitHub webhook delivery tab for errors

### Permission denied
- Verify app has required permissions
- Re-install app if permissions changed
- Check installation is active

### Token expired
- Installation tokens expire after 1 hour
- Implement token refresh in code
- Cache tokens with expiry time
