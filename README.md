# DocVoice AI – Google Cloud Run Backend

FastAPI backend for DocVoice AI, optimized for Google Cloud Run.

## Specs on Cloud Run
| Feature | Limit |
|---|---|
| File size | Up to **100 MB** |
| Timeout | **5 minutes** per request |
| Memory | **1 GB** |
| Free tier | 2 million requests/month |

---

## Prerequisites

1. Install Google Cloud CLI:
   https://cloud.google.com/sdk/docs/install-sdk#windows

2. Login:
   ```powershell
   gcloud init
   gcloud auth login
   ```

3. Create a project at https://console.cloud.google.com if you don't have one.

---

## Deploy (One Command)

```powershell
cd docvoice-backend
.\deploy.ps1
```

The script will ask for:
- Your **Google Cloud Project ID**
- Your **Vercel frontend URL** (for CORS)

It then deploys and prints your backend URL.

---

## Manual Deploy

```powershell
$PROJECT = "your-project-id"
$REGION  = "us-central1"

gcloud run deploy docvoice-backend `
  --source . `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --timeout 300 `
  --set-env-vars "TMP_DIR=/tmp/docvoice,MAX_UPLOAD_BYTES=104857600,ALLOWED_ORIGINS=https://your-app.vercel.app" `
  --project $PROJECT
```

---

## Connect to Vercel Frontend

After deploying, copy the Cloud Run URL (looks like):
```
https://docvoice-backend-xxxxxxxx-uc.a.run.app
```

Go to **Vercel → Project → Settings → Environment Variables** and add:
```
NEXT_PUBLIC_API_URL = https://docvoice-backend-xxxxxxxx-uc.a.run.app
```

Then **redeploy** the Vercel frontend.

---

## Update Environment Variables

```powershell
gcloud run services update docvoice-backend `
  --region us-central1 `
  --set-env-vars ALLOWED_ORIGINS=https://your-app.vercel.app
```

## View Logs

```powershell
gcloud run services logs read docvoice-backend --region us-central1 --limit 50
```

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/api/docs
