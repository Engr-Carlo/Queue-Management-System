@echo off
REM Emergency Audio Alert for Queue System
REM This batch file plays system sounds and shows alerts

echo [ALERT] EMERGENCY AUDIO ALERT FOR QUEUE %1!

REM Play system alert sound multiple times
for /L %%i in (1,1,5) do (
    echo [WARN] Playing system alert %%i/5...
    powershell -c "[console]::beep(880,1000)"
    timeout /t 1 /nobreak >nul
)

REM Try to play the alarm.wav file if it exists
if exist "Sounds\alarm.wav" (
    echo [AUDIO] Playing alarm.wav...
    powershell -c "(New-Object Media.SoundPlayer 'Sounds\alarm.wav').PlaySync()"
) else if exist "alarm.wav" (
    echo [AUDIO] Playing alarm.wav...
    powershell -c "(New-Object Media.SoundPlayer 'alarm.wav').PlaySync()"
) else (
    echo [ERROR] No alarm.wav file found
)

REM Show system notification using PowerShell
echo [INFO] Showing system notification...
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Queue Number %1 is being called!^n^nPlease proceed to the office immediately!', 'QUEUE ALERT!', 'OK', 'Warning')"

echo [OK] Emergency audio alert completed!
pause
