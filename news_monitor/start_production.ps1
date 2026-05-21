# News Monitor Production Startup Script
# Runs the system accessible from the internet

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "News Monitor System - Production Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get network information
$ipAddresses = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne "127.0.0.1"}).IPAddress
Write-Host "Server IP Addresses:" -ForegroundColor Green
foreach ($ip in $ipAddresses) {
    Write-Host "  - http://$ip:5000" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Access from internet using your public IP or domain name" -ForegroundColor Green
Write-Host ""

# Check if venv exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Warning: Virtual environment not found. Using system Python." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting News Monitor in Web Mode..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the application
python main.py --mode web --log-level INFO
