# GitHub App Localhost Setup - Quick Start

This guide walks you through setting up a GitHub App for **localhost development** using ngrok.

## Prerequisites

- Backend API running on `http://localhost:8000`
- Node.js installed (for smee-client)
- GitHub account

## Step-by-Step Setup

### Option A: Using Smee.io (Recommended - Simpler)

Smee.io is a free webhook proxy service specifically designed for GitHub webhooks. It's simpler than ngrok for this use case.

#### Step 1: Create Smee Channel

1. Go to https://smee.io/
2. Click **"Start a new channel"**
3. Copy the channel URL (e.g., `https://smee.io/ABC123xyz`)

#### Step 2: Install smee-client

```bash
npm install -g smee-client
```

#### Step 3: Start Smee Forwarding

Open a **new terminal** and run:

```bash
smee --url https://smee.io/YOUR_CHANNEL_ID --target http://localhost:8000/api/github/webhooks
```

Replace `YOUR_CHANNEL_ID` with your actual channel ID from step 1.

⚠️ **Important**: Keep this terminal open! Smee must stay running.

#### Step 4: Create GitHub App

Use the Smee URL in your GitHub App settings:

- **Webhook URL:** `https://smee.io/YOUR_CHANNEL_ID`
- **Callback URL:** `http://localhost:8000/api/auth/github/callback` (or use Smee URL if needed)

**Note**: Smee forwards webhooks to your localhost, so GitHub sends to Smee, and Smee forwards to your local server.

---

### Option B: Using ngrok (Alternative)

If you prefer ngrok or need a direct HTTPS tunnel:

#### Step 1: Install ngrok

**Windows:**
```powershell
# Option 1: Using Chocolatey
choco install ngrok

# Option 2: Download from https://ngrok.com/download
# Extract and add to PATH
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

### 2. Sign up for ngrok (Free)

1. Go to https://dashboard.ngrok.com/signup
2. Create a free account
3. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
4. Configure ngrok:
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
```

#### Step 3: Start ngrok Tunnel

Open a **new terminal** and run:

```bash
ngrok http 8000
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123-def456.ngrok-free.app -> http://localhost:8000
```

**Copy the HTTPS URL** (e.g., `https://abc123-def456.ngrok-free.app`)

⚠️ **Important**: Keep this terminal open! The tunnel must stay active.

#### Step 4: Create GitHub App (ngrok)

1. Go to: https://github.com/settings/apps/new

2. Fill in **Basic Information**:

   - **GitHub App name:** `InSpecThor Local Dev` (or any name)
   - **Description:** `Local development instance of InSpecThor`
   - **Homepage URL:** `https://abc123-def456.ngrok-free.app` (your ngrok URL)
   - **Callback URL:** `https://abc123-def456.ngrok-free.app/api/auth/github/callback`
   - **Setup URL:** (leave empty)
   - **Webhook URL:** `https://abc123-def456.ngrok-free.app/api/github/webhooks` (ngrok URL)
   
   **OR if using Smee:**
   - **Webhook URL:** `https://smee.io/YOUR_CHANNEL_ID` (Smee channel URL)
   - **Webhook secret:** Click "Generate a new secret" and **copy it** (you'll need it!)

3. Set **Repository permissions**:

   - **Contents:** Read
   - **Pull requests:** Read & write
   - **Checks:** Read & write
   - **Metadata:** Read (automatic)

4. Subscribe to events:

   - ✅ Push
   - ✅ Pull request
   - ✅ Installation
   - ✅ Installation repositories

5. **Where can this GitHub App be installed?**

   - Select: **Any account**

6. Click **"Create GitHub App"**

### 5. Get App Credentials (Both Options)

After creating the app, you'll be on the app settings page. Note down:

1. **App ID** (e.g., `123456`) - shown at the top
2. **Client ID** - under "About" section
3. **Client Secret** - Click "Generate a new client secret", copy it
4. **Private Key** - Scroll to "Private keys", click "Generate a private key"
   - Download the `.pem` file
   - Save it in your project root as `github-app-private-key.pem`
   - **Add to `.gitignore`**:
     ```bash
     echo "github-app-private-key.pem" >> .gitignore
     ```

### 6. Configure Environment Variables

Create or update `api/.env`:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456  # Your App ID from step 5
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_WEBHOOK_SECRET=your-webhook-secret-from-step-4
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxxx  # Your Client ID
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxx  # Your Client Secret

# OAuth Redirect (for user login)
GITHUB_OAUTH_REDIRECT_URI=http://localhost:3000/auth/github/callback
```

### 7. Start Your Backend

In a **separate terminal**:

```bash
cd api
# Make sure your .env file is configured
uvicorn main:app --reload --port 8000
```

### 8. Test Webhook Delivery

1. Go to your GitHub App settings: `https://github.com/settings/apps/YOUR_APP_NAME`
2. Click **"Advanced"** tab
3. Click **"Recent Deliveries"**
4. You should see a `ping` event delivery (GitHub sends this automatically)
5. Click on it to see the delivery details

If you see a **200 OK** response, webhooks are working! ✅

### 9. Install the App

1. Go to your GitHub App settings page
2. Click **"Install App"** button (top right)
3. Select your account or organization
4. Choose repositories:
   - **All repositories** (for testing)
   - Or **Only select repositories** (pick a test repo)
5. Click **"Install"**

### 10. Test with a Repository

1. Create a test repository (or use an existing one)
2. Make sure the app is installed on it
3. Push a commit or create a PR
4. Check your backend logs - you should see webhook events!

## Troubleshooting

### Smee Channel Not Working

1. **Check smee-client is running**: The terminal should show "Connected" messages
2. **Verify channel URL**: Make sure it matches in both GitHub App settings and smee command
3. **Check backend is running**: `curl http://localhost:8000/api/health`
4. **Restart smee**: Stop and restart the smee-client command

### ngrok URL Changed

If you restart ngrok, you'll get a new URL. You need to:

1. Update the GitHub App webhook URL:
   - Go to GitHub App settings
   - Update "Webhook URL" with new ngrok URL
   - Save changes

### Webhook Not Received

1. **Check ngrok is running**: Visit http://127.0.0.1:4040 to see ngrok dashboard
2. **Check backend is running**: `curl http://localhost:8000/api/health`
3. **Check webhook secret matches**: Must match in both GitHub App settings and `.env`
4. **Check GitHub webhook deliveries**: Go to App settings → Advanced → Recent Deliveries
   - Look for error messages
   - Check response status codes

### Permission Denied Errors

1. **Re-install the app** if you changed permissions
2. **Check installation is active**: Go to App settings → Installations
3. **Verify repository access**: Make sure app is installed on the repository

### Smee vs ngrok Comparison

| Feature | Smee.io | ngrok |
|---------|---------|-------|
| **Setup** | Very simple (just create channel) | Requires signup + authtoken |
| **URL Stability** | Channel URL never changes ✅ | Changes on restart (free plan) |
| **Purpose** | Specifically for webhooks | General HTTPS tunnel |
| **Cost** | Free | Free (with limitations) |
| **Best For** | GitHub webhooks | General development |

**Recommendation**: Use **Smee.io** for GitHub webhooks - it's simpler and the URL never changes!

## Next Steps

Once webhooks are working:

1. **Test push events**: Push a commit to a repository
2. **Test PR events**: Create a pull request
3. **Test verification**: The Cloud Bot should verify code and post check runs

## Production Deployment

When deploying to production:

1. Use a real domain (not ngrok)
2. Update GitHub App URLs to production domain
3. Use environment variables or secrets manager for credentials
4. Enable webhook signature verification
5. Set up proper SSL/TLS certificates

---

**Need help?** Check the main [GITHUB_APP_SETUP.md](./GITHUB_APP_SETUP.md) for more details.
