# AutoReply — Instagram Comment-to-DM Automation

Automatically reply to Instagram comments and send DMs when a user comments a keyword on one of your posts — no third-party services, official Graph API only.

---

## How it works

1. You create a **Campaign**: pick a post, set trigger keywords, write a comment reply and a DM.
2. A follower comments "link" (or any keyword you chose) on that post.
3. The webhook fires → the app replies publicly to the comment + sends a private DM.

---

## Quick start (local)

```bash
git clone <this-repo>
cd instagram-dm-tool
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
uvicorn main:app --reload
```

Open **http://localhost:8000** — the dashboard is at `/dashboard`.

---

## Instagram / Facebook API Setup (step-by-step)

### 1. Convert your Instagram account

Your Instagram account must be a **Business** or **Creator** account.

- Instagram app → Profile → ☰ → Settings → Account → Switch to Professional Account

### 2. Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com) → **My Apps** → **Create App**
2. Choose **Business** as the app type
3. Fill in App Name (e.g. "My AutoReply Bot") and contact email
4. On the dashboard, click **Add Product** → find **Instagram Graph API** → **Set up**

### 3. Add required permissions

In your app, go to **App Review → Permissions and Features** and request:

| Permission | Purpose |
|---|---|
| `instagram_manage_comments` | Read comments and post replies |
| `instagram_manage_messages` | Send DMs (**see note below**) |
| `pages_show_list` | List your Facebook Pages |
| `instagram_basic` | Access basic IG account info |

> ⚠️ **DM permission note:** `instagram_manage_messages` requires Facebook App Review approval with a demonstrated use case. Until approved, DMs will only work if the user has previously messaged your business account. Apply via: App Dashboard → App Review → Permissions → `instagram_manage_messages` → Request Advanced Access.

### 4. Generate a Long-Lived User Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your App in the top-right dropdown
3. Click **Generate Access Token** and grant all required permissions
4. You'll get a **short-lived token** (valid ~1 hour). Exchange it for a long-lived one:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token\
?grant_type=fb_exchange_token\
&client_id=YOUR_APP_ID\
&client_secret=YOUR_APP_SECRET\
&fb_exchange_token=SHORT_LIVED_TOKEN"
```

The response contains a token valid for **60 days**.

#### Refreshing the token before it expires

Long-lived tokens auto-extend when used within the 60-day window. To manually refresh:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token\
?grant_type=fb_exchange_token\
&client_id=YOUR_APP_ID\
&client_secret=YOUR_APP_SECRET\
&fb_exchange_token=CURRENT_LONG_LIVED_TOKEN"
```

Run this in a cron job every 30 days and update `INSTAGRAM_ACCESS_TOKEN` in your `.env`.

### 5. Get your Page ID and Instagram Business Account ID

```bash
# Get Pages linked to your token
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_TOKEN"

# Get IG Business Account ID linked to a Page
curl "https://graph.facebook.com/v19.0/PAGE_ID?fields=instagram_business_account&access_token=YOUR_TOKEN"
```

### 6. Get a Post ID for a specific Instagram post

In [Graph API Explorer](https://developers.facebook.com/tools/explorer/):

```
GET /{ig-business-account-id}/media?fields=id,caption,timestamp,media_type
```

The `id` field in each result is your Post ID. You can also get it from the post URL on Instagram desktop (the string after `/p/`) by converting the shortcode — or directly via the API as shown above.

### 7. Configure the Webhook

1. In your Facebook App → **Webhooks** → **Add Subscription** → choose **Instagram**
2. Set:
   - **Callback URL**: `https://your-app.railway.app/webhook/instagram`
   - **Verify Token**: the same random string you put in `WEBHOOK_VERIFY_TOKEN`
3. Subscribe to the **`comments`** field
4. Click **Verify and Save**

Your app must be publicly accessible (deployed) for Facebook to reach it. For local testing, use [ngrok](https://ngrok.com): `ngrok http 8000` and use the HTTPS URL.

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived User Access Token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Your IG Business Account ID |
| `FACEBOOK_APP_SECRET` | App Secret from your Facebook Developer App |
| `WEBHOOK_VERIFY_TOKEN` | Any random string — must match what you put in the webhook setup |
| `DATABASE_URL` | SQLite path (default) or `postgresql://…` for production |

---

## Project structure

```
├── main.py              # FastAPI entry point
├── instagram.py         # Graph API client (reply, DM, post details)
├── models.py            # SQLAlchemy models (Config, Campaign, ProcessedComment)
├── database.py          # DB session setup
├── routes/
│   ├── webhook.py       # GET/POST /webhook/instagram
│   ├── dashboard.py     # Serves the HTML dashboard
│   └── api.py           # REST API for campaigns & config
├── static/
│   ├── css/dashboard.css
│   └── js/dashboard.js
├── templates/
│   └── dashboard.html
├── .env.example
├── Dockerfile
├── railway.toml
├── render.yaml
└── requirements.txt
```

---

## Deployment

### Railway

1. Push this repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Add environment variables in the Railway dashboard
4. Railway auto-detects `railway.toml` and builds with Docker

### Render

1. Push to GitHub
2. New Render Web Service → connect repo
3. Render reads `render.yaml` automatically
4. Add secret environment variables in the Render dashboard

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status":"ok"}` |
| `GET` | `/dashboard` | Web dashboard |
| `GET` | `/webhook/instagram` | Facebook webhook verification |
| `POST` | `/webhook/instagram` | Incoming comment events |
| `GET` | `/api/config` | Load saved credentials |
| `POST` | `/api/config` | Save credentials |
| `POST` | `/api/config/verify` | Test connection to Instagram |
| `GET` | `/api/campaigns` | List all campaigns |
| `POST` | `/api/campaigns` | Create a campaign |
| `PATCH` | `/api/campaigns/{id}` | Update a campaign |
| `DELETE` | `/api/campaigns/{id}` | Delete a campaign |
| `POST` | `/api/campaigns/{id}/toggle` | Toggle active/inactive |
| `GET` | `/api/post-preview` | Fetch post thumbnail + caption |

---

## Security notes

- Webhook signatures are validated via `X-Hub-Signature-256` using your `FACEBOOK_APP_SECRET`
- Credentials are never exposed to the frontend (the dashboard reads/writes via the API)
- Set `FACEBOOK_APP_SECRET` in production — without it, signature validation is skipped (dev mode only)
- Duplicate comment processing is prevented via the `ProcessedComment` table

---

## Limitations & gotchas

- **DMs**: require `instagram_manage_messages` with approved Advanced Access. Without it, DMs only work if the user has previously contacted your business. Apply for access in your Facebook App → App Review.
- **Tokens expire**: Long-lived tokens last 60 days. Set up a cron job to refresh them.
- **Rate limits**: The Graph API enforces rate limits. The client automatically retries with exponential backoff on codes 4, 32, and 613.
- **Webhook delivery**: Facebook may retry failed webhooks. The `ProcessedComment` deduplication table prevents double-replies.
- **Only official APIs**: this tool uses only the official Instagram Graph API. No Selenium, no `instagrapi`, no unofficial methods.
