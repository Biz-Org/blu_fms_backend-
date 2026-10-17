@echo off
REM Start Odoo with a single clean process (avoids broken CSS from duplicate servers).
cd /d "%~dp0..\..\.."

echo Stopping any existing Odoo on port 8069...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8069" ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo Checking PostgreSQL on 5433...
netstat -ano | findstr ":5433" | findstr LISTENING >nul
if errorlevel 1 (
  echo Starting PostgreSQL...
  "C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe" start -D "C:\Program Files\PostgreSQL\16\data" -l "%~dp0..\..\..\pg_startup.log" -w
)

echo Starting Odoo (one instance only)...
call venv\Scripts\activate.bat
python odoo-bin -c odoo.conf
