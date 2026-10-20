$ErrorActionPreference = 'Stop'
$evidencePath = Join-Path $PSScriptRoot 'phase13-evidence'
$sample = Get-ChildItem -LiteralPath $evidencePath -Filter 'SpecTrace_AI_*.xlsx' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $sample) { throw 'No downloaded XLSX sample' }
$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($sample.FullName, 0, $true)
    $sheets = @()
    for ($index = 1; $index -le $workbook.Worksheets.Count; $index++) {
        $sheet = $workbook.Worksheets.Item($index)
        $sheets += @{ name = $sheet.Name; rows = $sheet.UsedRange.Rows.Count; columns = $sheet.UsedRange.Columns.Count }
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($sheet)
    }
    $result = @{ application = 'Microsoft Excel'; version = $excel.Version; openedReadOnly = $workbook.ReadOnly; file = $sample.Name; sheets = $sheets; sheetCount = $workbook.Worksheets.Count; success = $true }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $evidencePath 'excel-desktop-reopen.json') -Encoding UTF8
    Write-Output "Excel reopened workbook: $($sheets.Count) sheets, ReadOnly=$($workbook.ReadOnly)"
} finally {
    if ($workbook) { $workbook.Close($false); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
    if ($excel) { $excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
