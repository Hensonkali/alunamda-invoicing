# ALUNAMDA Invoicing - Fly.io Deployment Script
# Run this from the alunamda-cloud directory

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ALUNAMDA Invoicing - Fly.io Deploy    " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if flyctl is installed
$flyPath = "$env:USERPROFILE\.fly\bin\flyctl.exe"
if (-not (Test-Path $flyPath)) {
    Write-Host "ERROR: flyctl not found at $flyPath" -ForegroundColor Red
    Write-Host "Install it: iwr https://fly.io/install.ps1 -useb | iex" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Logging in to Fly.io..." -ForegroundColor Yellow
& $flyPath auth login
if ($LASTEXITCODE -ne 0) {
    Write-Host "Login failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  Logged in!" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] Generating secure keys..." -ForegroundColor Yellow
$secretKey = python -c "import secrets; print(secrets.token_hex(32))"
$csrfKey = python -c "import secrets; print(secrets.token_hex(32))"
Write-Host "  Keys generated!" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] Creating Fly.io app..." -ForegroundColor Yellow
& $flyPath apps create alunamda-invoicing --json 2>$null | Out-Null
Write-Host "  App created!" -ForegroundColor Green

Write-Host ""
Write-Host "[4/5] Creating persistent volume..." -ForegroundColor Yellow
$region = "jnb"
& $flyPath volumes create alunamda_data --app alunamda-invoicing --region $region --size 1 2>$null | Out-Null
Write-Host "  Volume created in $region!" -ForegroundColor Green

Write-Host ""
Write-Host "[5/5] Setting secrets..." -ForegroundColor Yellow
& $flyPath secrets set "SECRET_KEY=$secretKey" "CSRF_SECRET_KEY=$csrfKey" --app alunamda-invoicing
Write-Host "  Secrets configured!" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deployment ready!                     " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Deploy with:" -ForegroundColor Cyan
Write-Host "  flyctl deploy" -ForegroundColor White
Write-Host ""
Write-Host "After deployment, your app is live at:" -ForegroundColor Cyan
Write-Host "  https://alunamda-invoicing.fly.dev" -ForegroundColor White
Write-Host ""
Write-Host "View logs:" -ForegroundColor Cyan
Write-Host "  flyctl logs" -ForegroundColor White
Write-Host ""
Write-Host "Monitor:" -ForegroundColor Cyan
Write-Host "  flyctl status" -ForegroundColor White
