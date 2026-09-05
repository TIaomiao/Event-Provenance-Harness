[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$remoteStatusRoot = '/home/Larry/code/Ziqiu/LabelSystem/zian_workspace/ehr_pipeline/research_harness_week1/status'
$snapshotRoot = Join-Path $PSScriptRoot ('remote_status/' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
New-Item -ItemType Directory -Path $snapshotRoot -ErrorAction Stop | Out-Null

foreach ($name in @('implementation.md', 'evaluation.md')) {
    $localTarget = Join-Path $snapshotRoot $name
    & scp -q -o BatchMode=yes -o ConnectTimeout=12 "Larry:${remoteStatusRoot}/$name" $localTarget
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to fetch $name; this snapshot is incomplete."
    }
    $localDigest = (Get-FileHash -LiteralPath $localTarget -Algorithm SHA256).Hash.ToLowerInvariant()
    $remoteResult = & ssh -o BatchMode=yes -o ConnectTimeout=12 Larry "sha256sum '$remoteStatusRoot/$name'"
    if ($LASTEXITCODE -ne 0) { throw "Failed to verify $name." }
    $remoteDigest = ($remoteResult -split '\s+')[0]
    if ($localDigest -ne $remoteDigest) {
        throw "Digest mismatch for $name; a remote update may be in progress. Run again."
    }
    Write-Output "$name verified"
}
Write-Output "Snapshot: $snapshotRoot"
