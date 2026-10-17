@echo off
REM Run plant maintenance automated tests.
cd /d "%~dp0..\..\.."
call venv\Scripts\activate.bat
python odoo-bin -c odoo.conf -d odoo_dev --test-tags /maintenance:TestEquipmentExcelImport,/maintenance:TestWorkOrderFlow,/maintenance:TestPlantMaintenanceRoles --stop-after-init --log-level=test
pause
