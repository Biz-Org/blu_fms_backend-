@echo off
REM Upgrade plant maintenance module (run from anywhere).
cd /d "%~dp0..\..\.."
echo Upgrading maintenance module on odoo_dev...
call venv\Scripts\activate.bat
python odoo-bin -c odoo.conf -u maintenance -d odoo_dev --stop-after-init
if errorlevel 1 (
  echo Upgrade FAILED.
  pause
  exit /b 1
)
echo Done. Restart Odoo and press Ctrl+Shift+R in the browser.
pause
