# LinkedIn Assistant — Claude Development Protocol

## GitHub Push Protocol

This project follows the global 48-hour GitHub refresh rule (see global CLAUDE.md rule #12):

> Every project is hosted at https://github.com/akanturker-dev. 
> **48-hour automatic refresh:** If 48 hours have passed without a push, an automatic push is performed 
> (even if there are no changes—using an empty commit). This keeps the repository appearing active 
> and serves as a live proof of work.

### Setup

To enable automatic 48-hour refresh:

1. **Via Task Scheduler (Recommended):**
   - Open Task Scheduler (`taskschd.msc`)
   - Create a new task with these settings:
     - **Trigger:** Daily at 2:00 AM
     - **Action:** Run program `powershell.exe`
     - **Arguments:** `-NoProfile -ExecutionPolicy Bypass -File "git-refresh.ps1"`
     - **Location:** The repository root directory

2. **Manual trigger:**
   - Double-click `git-refresh.cmd` to run the refresh check immediately

### How it works

- **`git-refresh.ps1`** — Checks if 48 hours have passed since last push. If yes, creates an empty commit and pushes.
- **`git-refresh.cmd`** — Wrapper for running the PowerShell script from Explorer.
- **`.lastpush` file** — Tracks the timestamp of the last automatic push (created automatically).

### Repository

- **URL:** https://github.com/akanturker-dev/linkedn
- **Branch:** main
- **Visibility:** Public

### Notes

- The refresh only triggers if 48 hours have passed (checked by `.lastpush` timestamp).
- Empty commits are created with message: "48-hour GitHub refresh - Automatic push"
- No manual action is required; the system works automatically.
