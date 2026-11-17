param(
    [string]$ProjectId = "jarvis-2112",
    [string]$Region = "asia-south1",
    [string]$AllowedEmail = "sandarikarimurari2014@gmail.com"
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE. Complete the sign-in or setup step shown above, then run this file again."
    }
}

$firebase = Get-Command firebase -ErrorAction SilentlyContinue
$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $firebase) { throw "Firebase CLI is missing. Install it, then sign in with $AllowedEmail using: firebase login" }
if (-not $gcloud) { throw "Google Cloud CLI is missing. Install it and sign in with the Google account for project $ProjectId." }

$envFile = Join-Path (Get-Location) ".env"
$geminiKey = $env:GEMINI_API_KEY
if (-not $geminiKey -and (Test-Path -LiteralPath $envFile)) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*GEMINI_API_KEY\s*=\s*(.*)\s*$') {
            $geminiKey = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}
if (-not $geminiKey) { throw "Add your Gemini key to GEMINI_API_KEY in .env before deploying. The key will be stored in Google Secret Manager, not in the website." }

Write-Host "Deploying the JARVIS server to Cloud Run in $Region..."
Invoke-Checked "gcloud" @("config", "set", "project", $ProjectId)
Invoke-Checked "gcloud" @("services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com", "--project", $ProjectId)

$secretName = "jarvis-gemini-api-key"
& gcloud secrets describe $secretName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Checked "gcloud" @("secrets", "create", $secretName, "--replication-policy=automatic", "--project", $ProjectId)
}
$secretFile = Join-Path ([System.IO.Path]::GetTempPath()) ("jarvis-secret-" + [guid]::NewGuid().ToString("N") + ".txt")
try {
    [System.IO.File]::WriteAllText($secretFile, $geminiKey, [System.Text.UTF8Encoding]::new($false))
    Invoke-Checked "gcloud" @("secrets", "versions", "add", $secretName, "--data-file=$secretFile", "--project", $ProjectId)
} finally {
    if (Test-Path -LiteralPath $secretFile) { Remove-Item -LiteralPath $secretFile -Force }
    $geminiKey = $null
}

$projectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $projectNumber) { throw "Could not read the Google Cloud project number." }
$runtimeAccount = "$projectNumber-compute@developer.gserviceaccount.com"
Invoke-Checked "gcloud" @("secrets", "add-iam-policy-binding", $secretName, "--member=serviceAccount:$runtimeAccount", "--role=roles/secretmanager.secretAccessor", "--project", $ProjectId)

Invoke-Checked "gcloud" @(
    "run", "deploy", "jarvis-api", "--source", ".", "--region", $Region, "--project", $ProjectId,
    "--allow-unauthenticated", "--max", "1", "--memory", "1Gi", "--timeout", "60s",
    "--set-env-vars", "FIREBASE_AUTH_REQUIRED=true,FIREBASE_PROJECT_ID=$ProjectId,JARVIS_ALLOWED_EMAILS=$AllowedEmail,JARVIS_RATE_LIMIT_REQUESTS=20,JARVIS_AUDIT_PATH=/tmp/jarvis-audit/events.jsonl",
    "--set-secrets", "GEMINI_API_KEY=$secretName`:latest"
)

Write-Host "Deploying the dashboard to Firebase Hosting..."
Invoke-Checked "firebase" @("deploy", "--only", "hosting", "--project", $ProjectId)
Write-Host "JARVIS is deployed at https://$ProjectId.web.app"
