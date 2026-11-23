Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   Starting DevOps Monitoring & Logging Platform...    " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

docker compose up -d

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "   DevOps Monitoring Platform is Ready!                " -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "   [Dashboard]   " -NoNewline
Write-Host "http://localhost:5000" -ForegroundColor Yellow -NoNewline
Write-Host "  (Hold Ctrl and Click)"
Write-Host "   [Grafana]     " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Yellow -NoNewline
Write-Host "  (Hold Ctrl and Click)"
Write-Host "   [Prometheus]  " -NoNewline
Write-Host "http://localhost:9090" -ForegroundColor Yellow
Write-Host "   [Alerts]      " -NoNewline
Write-Host "http://localhost:9093" -ForegroundColor Yellow
Write-Host "   [cAdvisor]    " -NoNewline
Write-Host "http://localhost:8888" -ForegroundColor Yellow
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""

# Automatically open in default browser (Chrome / Edge)
Start-Process "http://localhost:5000"
