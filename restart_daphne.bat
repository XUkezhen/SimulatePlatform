@echo off
setlocal

echo restart_daphne.bat is deprecated. Redirecting to restart_backend_pm2.bat...
call "%~dp0restart_backend_pm2.bat"
exit /b %errorlevel%
