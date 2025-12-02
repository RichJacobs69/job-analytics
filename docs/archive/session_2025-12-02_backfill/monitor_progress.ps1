# Monitor job classification progress
# Usage: .\monitor_progress.ps1

Write-Host "Monitoring job progress..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop monitoring`n" -ForegroundColor Yellow

$jobs = Get-Job

if (-not $jobs) {
    Write-Host "No background jobs found. Make sure jobs are running." -ForegroundColor Red
    exit
}

while ($true) {
    Clear-Host
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host "JOB PROGRESS MONITOR" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host ""
    
    foreach ($job in $jobs) {
        $output = $job | Receive-Job -Keep
        
        # Extract progress information
        $progressLines = $output | Select-String "Progress:"
        $lastProgress = $progressLines | Select-Object -Last 1
        
        # Extract total jobs count
        $totalJobs = $output | Select-String "Classifying \d+ jobs" | ForEach-Object {
            if ($_ -match "Classifying (\d+) jobs") { $matches[1] }
        } | Select-Object -Last 1
        
        # Count API calls (successful)
        $apiCalls = ($output | Select-String "HTTP Request.*200 OK").Count
        
        # Count rate limits
        $rateLimits = ($output | Select-String "429 Too Many Requests").Count
        
        # Count retries
        $retries = ($output | Select-String "Retrying request").Count
        
        Write-Host "Job ID: $($job.Id) | State: $($job.State)" -ForegroundColor $(if ($job.State -eq 'Running') { 'Green' } else { 'Yellow' })
        
        if ($lastProgress) {
            Write-Host "  Last Progress: $($lastProgress.Line.Trim())" -ForegroundColor White
        }
        
        if ($totalJobs) {
            Write-Host "  Total Jobs: $totalJobs" -ForegroundColor Gray
        }
        
        Write-Host "  API Calls (200 OK): $apiCalls" -ForegroundColor Green
        Write-Host "  Rate Limits (429): $rateLimits" -ForegroundColor Yellow
        Write-Host "  Retries: $retries" -ForegroundColor Yellow
        
        if ($lastProgress -and $totalJobs) {
            if ($lastProgress -match "Progress: (\d+)/(\d+)") {
                $current = [int]$matches[1]
                $total = [int]$matches[2]
                $remaining = $total - $current
                $percent = [math]::Round(($current / $total) * 100, 1)
                
                Write-Host "  Status: $current/$total ($percent%) | Remaining: $remaining" -ForegroundColor Cyan
            }
        }
        
        Write-Host ""
    }
    
    Write-Host "Refreshing in 5 seconds... (Press Ctrl+C to stop)" -ForegroundColor Gray
    Start-Sleep -Seconds 5
}

