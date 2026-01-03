# Logo and Favicon Update Script
# Updates logo references and favicon links across all HTML files

$files = Get-ChildItem -Filter "*.html" | Where-Object { $_.Name -notlike "test-*" -and $_.Name -notlike "api-*" -and $_.Name -notlike "audio-*" }

foreach ($file in $files) {
    Write-Host "Processing $($file.Name)..." -ForegroundColor Cyan
    
    $content = Get-Content $file.FullName -Raw
    $originalContent = $content
    
    # Replace old favicon
    $content = $content -replace '<link rel="icon" type="image/png" href="images/favicon.png">', '<link rel="icon" type="image/svg+xml" href="images/favicon-32x32.svg">'
    
    # Add apple-touch-icon if not present
    if ($content -notmatch 'apple-touch-icon') {
        $content = $content -replace '(<link rel="icon"[^>]+>)', "`$1`n  <link rel=`"apple-touch-icon`" sizes=`"180x180`" href=`"images/apple-touch-icon.svg`">"
    }
    
    # Replace Queue-logo.jpg with logo.svg
    $content = $content -replace 'images/Queue-logo\.jpg', 'images/logo.svg'
    
    # Update Font Awesome CDN version and add custom icon script
    if ($content -match 'font-awesome' -and $content -notmatch 'icons\.js') {
        $content = $content -replace '(<head>)', "`$1`n  <script src=`"icons.js`"></script>"
    }
    
    if ($content -ne $originalContent) {
        Set-Content -Path $file.FullName -Value $content -NoNewline
        Write-Host "  Updated $($file.Name)" -ForegroundColor Green
    } else {
        Write-Host "  No changes needed in $($file.Name)" -ForegroundColor Gray
    }
}

Write-Host "Logo and favicon update complete!" -ForegroundColor Green
