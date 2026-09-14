# GitHub 48-hour refresh script
$repoPath = "G:\Claude Projects\Asistanlar\linkedn"
$lastPushFile = "$repoPath\.lastpush"

if (-not (Test-Path $lastPushFile)) {
    $lastPushTime = (Get-Date).AddDays(-3)
} else {
    try {
        $lastPushTime = [datetime]::ParseExact((Get-Content $lastPushFile -Raw).Trim(), "yyyy-MM-dd HH:mm:ss", $null)
    } catch {
        $lastPushTime = (Get-Date).AddDays(-3)
    }
}

$timeDiff = (Get-Date) - $lastPushTime

if ($timeDiff.TotalHours -ge 48) {
    Set-Location $repoPath
    & git commit --allow-empty -m "48-hour GitHub refresh - Automatic push" 2>&1 | Out-Null
    & git push 2>&1 | Out-Null
    (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") | Set-Content $lastPushFile -Encoding utf8
}
