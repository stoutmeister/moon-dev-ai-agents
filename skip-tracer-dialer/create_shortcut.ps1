# PowerShell script to create a desktop shortcut for the Skip Tracer Dashboard

# Get paths
$scriptPath = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$launcherBat = Join-Path $scriptPath "launch_dashboard.bat"
$desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$shortcutPath = Join-Path $desktopPath "Skip Tracer Dashboard.lnk"

# Create shortcut
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherBat
$shortcut.WorkingDirectory = $scriptPath
$shortcut.Description = "Launch the Skip Tracer Dashboard for wholesaling leads"
$shortcut.IconLocation = "C:\Windows\System32\globe.ico"  # Browser icon
$shortcut.Save()

Write-Host ""
Write-Host "✅ Desktop shortcut created successfully!"
Write-Host ""
Write-Host "Shortcut location: $shortcutPath"
Write-Host ""
Write-Host "You can now double-click the 'Skip Tracer Dashboard' icon on your desktop"
Write-Host "to launch the web dashboard."
Write-Host ""
