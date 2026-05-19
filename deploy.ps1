# DocVoice AI – Google Cloud Run Deployment Script
# Run from the docvoice-backend\ folder:
#   .\deploy.ps1
#
# Prerequisites:
#   1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install-sdk#windows
#   2. Run: gcloud init && gcloud auth login

param(
    [string]$ProjectId    = "",
    [string]$Region       = "us-central1",
    [string]$ServiceName  = "docvoice-backend",
    [string]$FrontendUrl  = ""
)

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  ✔ $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "  ✘ $msg" -ForegroundColor Red; exit 1 }

# ── Check gcloud ──────────────────────────────────────────────────────────────
Write-Step "Checking Google Cloud CLI"
try {
    $v = gcloud version --format="value(Google Cloud SDK)" 2>&1
    Write-Ok "gcloud found"
} catch {
    Write-Fail "gcloud not found. Install from https://cloud.google.com/sdk/docs/install-sdk#windows"
}

# ── Project ID ────────────────────────────────────────────────────────────────
if (-not $ProjectId) {
    $ProjectId = gcloud config get-value project 2>&1
    if (-not $ProjectId -or $ProjectId -eq "(unset)") {
        $ProjectId = Read-Host "Enter your Google Cloud Project ID"
    }
}
Write-Ok "Project: $ProjectId"

# ── Frontend URL ──────────────────────────────────────────────────────────────
if (-not $FrontendUrl) {
    $FrontendUrl = Read-Host "Enter your Vercel frontend URL (e.g. https://docvoice-ai.vercel.app)"
}

# ── Enable APIs ───────────────────────────────────────────────────────────────
Write-Step "Enabling required Google Cloud APIs"
gcloud services enable `
    cloudbuild.googleapis.com `
    run.googleapis.com `
    containerregistry.googleapis.com `
    --project $ProjectId
Write-Ok "APIs enabled"

# ── Deploy to Cloud Run ───────────────────────────────────────────────────────
Write-Step "Deploying to Cloud Run (this takes 3-5 minutes first time)"
Write-Host "  Region:  $Region" -ForegroundColor DarkGray
Write-Host "  Service: $ServiceName" -ForegroundColor DarkGray

gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --timeout 300 `
    --concurrency 10 `
    --min-instances 0 `
    --max-instances 5 `
    --set-env-vars "TMP_DIR=/tmp/docvoice,MAX_UPLOAD_BYTES=104857600,MAX_TEXT_CHARS=200000,ALLOWED_ORIGINS=$FrontendUrl" `
    --project $ProjectId

# ── Get service URL ───────────────────────────────────────────────────────────
Write-Step "Getting service URL"
$ServiceUrl = gcloud run services describe $ServiceName `
    --region $Region `
    --project $ProjectId `
    --format "value(status.url)"

Write-Ok "Deployed successfully!"
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  🎉 DocVoice AI Backend is live!" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend URL : $ServiceUrl" -ForegroundColor Cyan
Write-Host "  Health check: $ServiceUrl/api/health" -ForegroundColor Cyan
Write-Host "  API docs    : $ServiceUrl/api/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next step: Add this to Vercel environment variables:" -ForegroundColor Yellow
Write-Host "  NEXT_PUBLIC_API_URL = $ServiceUrl" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

# Open health check in browser
Start-Sleep -Seconds 2
Start-Process "$ServiceUrl/api/health"
