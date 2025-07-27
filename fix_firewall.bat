@echo off
echo Checking if Python/Flask is allowed through Windows Firewall...
echo.
echo To fix firewall issues, run these commands as Administrator:
echo.
echo netsh advfirewall firewall add rule name="Python Flask" dir=in action=allow protocol=TCP localport=5000
echo netsh advfirewall firewall add rule name="Python Flask" dir=out action=allow protocol=TCP localport=5000
echo.
echo Press any key to continue...
pause > nul
