@echo off
setlocal

echo Restarting backend via PM2...
pm2 restart backend
exit /b %errorlevel%
