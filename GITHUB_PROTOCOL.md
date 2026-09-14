# GitHub 48-Hour Refresh Protocol

This project implements automatic GitHub repository refresh every 48 hours (empty commit + push) to maintain repo activity log.

## Setup

Run this once in admin PowerShell:
``powershell
.\setup-git-refresh-task.ps1
``

Or manually via Windows Task Scheduler:
- Trigger: Daily at 2:00 AM
- Action: Run powershell.exe with args: `-NoProfile -ExecutionPolicy Bypass -File "git-refresh.ps1"`

## Files

- `git-refresh.ps1` - Main refresh logic
- `git-refresh.cmd` - Wrapper for manual execution
- `.lastpush` - Timestamp of last push (created automatically)
