# Read-only diagnostics: no credentials, environment dump or system changes.
$ErrorActionPreference = 'Stop'
Write-Output "PowerShell: $($PSVersionTable.PSVersion)"
Get-Command python, py, git, psql, pg_ctl -ErrorAction SilentlyContinue | Select-Object Name, Source | Format-Table
python --version
git --version
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, @{Name='RAMTotalGiB';Expression={[math]::Round($_.TotalVisibleMemorySize / 1MB, 2)}}, @{Name='RAMFreeGiB';Expression={[math]::Round($_.FreePhysicalMemory / 1MB, 2)}} | Format-List
Get-PSDrive C | Select-Object Name, @{Name='DiskFreeGiB';Expression={[math]::Round($_.Free / 1GB, 2)}} | Format-List
