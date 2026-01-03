# Color Theme Update Script
# Replaces red/purple colors with blue theme across HTML files

$files = @(
    "home.html",
    "index.html",
    "queue-number.html",
    "queue-status.html",
    "admin-login.html",
    "admin-dashboard.html"
)

$colorReplacements = @{
    # Red to Blue
    '#dc2626' = '#3b82f6'   # Primary red -> Primary blue
    '#b91c1c' = '#1d4ed8'   # Dark red -> Dark blue
    '#991b1b' = '#1e40af'   # Darker red -> Darker blue
    '#ef4444' = '#60a5fa'   # Light red -> Light blue
    '#fef2f2' = '#dbeafe'   # Very light red -> Very light blue
    '#fee2e2' = '#bfdbfe'   # Light red bg -> Light blue bg
    
    # Purple to Blue
    '#667eea' = '#3b82f6'   # Purple -> Primary blue
    '#764ba2' = '#1d4ed8'   # Dark purple -> Dark blue
    
    # RGB equivalents
    'rgba(220, 38, 38' = 'rgba(59, 130, 246'   # Red rgba -> Blue rgba
    'rgba(185, 28, 28' = 'rgba(29, 78, 216'    # Dark red rgba -> Dark blue rgba
    'rgba(102, 126, 234' = 'rgba(59, 130, 246' # Purple rgba -> Blue rgba
    'rgba(118, 75, 162' = 'rgba(29, 78, 216'   # Dark purple rgba -> Dark blue rgba
}

foreach ($file in $files) {
    $filePath = Join-Path $PSScriptRoot $file
    
    if (Test-Path $filePath) {
        Write-Host "Processing $file..." -ForegroundColor Cyan
        
        $content = Get-Content $filePath -Raw
        $originalContent = $content
        
        foreach ($oldColor in $colorReplacements.Keys) {
            $newColor = $colorReplacements[$oldColor]
            $content = $content -replace [regex]::Escape($oldColor), $newColor
        }
        
        if ($content -ne $originalContent) {
            Set-Content -Path $filePath -Value $content -NoNewline
            Write-Host "  Updated $file" -ForegroundColor Green
        } else {
            Write-Host "  No changes needed in $file" -ForegroundColor Gray
        }
    } else {
        Write-Host "  File not found: $file" -ForegroundColor Red
    }
}

Write-Host "Color theme update complete!" -ForegroundColor Green
