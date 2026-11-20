# صدى — تشغيل محلي بنقرة واحدة (Windows / PowerShell)
# يفتح ثلاث نوافذ: Sada AI (8100) ، Backend (8000) ، Frontend (5173) ثم يفتح المتصفح.
# المتطلبات: Python 3.11+ و Node 18+ على PATH. يستخدم SQLite فلا حاجة لـ PostgreSQL.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "✗ $cmd غير موجود. $hint" -ForegroundColor Red; exit 1 }
}
Need python "ثبّت Python من python.org وفعّل Add to PATH."
Need npm    "ثبّت Node.js LTS من nodejs.org."

# ---------- 1) Sada AI ----------
if (-not (Test-Path "ai-service\.venv")) {
  Write-Host "▶ إنشاء بيئة Sada AI وتثبيت المتطلبات…" -ForegroundColor Cyan
  python -m venv ai-service\.venv
  & ai-service\.venv\Scripts\pip.exe install -q -r ai-service\requirements.txt
}
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\ai-service'; .\.venv\Scripts\Activate.ps1; `$host.UI.RawUI.WindowTitle='Sada AI :8100'; uvicorn app.main:app --port 8100"

# ---------- 2) Backend ----------
if (-not (Test-Path "backend\.venv")) {
  Write-Host "▶ إنشاء بيئة الـ backend وتثبيت المتطلبات…" -ForegroundColor Cyan
  python -m venv backend\.venv
  & backend\.venv\Scripts\pip.exe install -q -r backend\requirements.txt
}
New-Item -ItemType Directory -Force -Path backend\var | Out-Null
$env:SADA_DATABASE_URL = "sqlite:///./var/dev.db"
$env:SADA_EVIDENCE_DIR = "./var/evidence"
$env:SADA_AI_SERVICE_URL = "http://localhost:8100"
Push-Location backend
& .\.venv\Scripts\python.exe -m scripts.seed
Pop-Location
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\backend'; .\.venv\Scripts\Activate.ps1; `$env:SADA_DATABASE_URL='sqlite:///./var/dev.db'; `$env:SADA_EVIDENCE_DIR='./var/evidence'; `$env:SADA_AI_SERVICE_URL='http://localhost:8100'; `$host.UI.RawUI.WindowTitle='Sada Backend :8000'; uvicorn app.main:app --port 8000 --reload"

# ---------- 3) Frontend ----------
if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "▶ تثبيت حزم الواجهة (npm install)…" -ForegroundColor Cyan
  Push-Location frontend; npm install --silent; Pop-Location
}
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\frontend'; `$host.UI.RawUI.WindowTitle='Sada Frontend :5173'; npm run dev"

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173/login"

Write-Host ""
Write-Host "✓ الخدمات تعمل:" -ForegroundColor Green
Write-Host "   الواجهة   http://localhost:5173"
Write-Host "   الـ API   http://localhost:8000/docs"
Write-Host "   Sada AI   http://localhost:8100/docs"
Write-Host ""
Write-Host "حسابات الدخول:"
Write-Host "   عميل      ahmad.mansouri@example.com   Customer#2026"
Write-Host "   مراجِعة   maryam.review@sada.example   Reviewer#2026"
Write-Host "   مدير      abdullah.admin@sada.example  Admin#2026"
Write-Host "   مستفيد للتحويل: حساب 100058329017 (نورة العتيبي)"
Write-Host ""
Write-Host "لإيقاف الخدمات: أغلق النوافذ الثلاث." -ForegroundColor Yellow
