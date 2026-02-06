# PowerShell Script to rename agentcore to agentcore
# Excludes the frontend folder from all changes

param(
    [switch]$DryRun = $false,
    [string]$RootPath = "D:\Code_clean_branch\aimldevteam\agentcore"
)

$OldName = "agentcore"
$NewName = "agentcore"
$OldNameCamel = "Agentcore"
$NewNameCamel = "Agentcore"
$OldNameUpper = "AGENTCORE"
$NewNameUpper = "AGENTCORE"

# Exclusion patterns
$ExcludeFolders = @(
    "frontend",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    "chroma",
    ".ruff_cache"
)

# File extensions to process for content replacement
$TextFileExtensions = @(
    ".py", ".pyi", ".pyx",
    ".txt", ".md", ".mdx", ".rst",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".htm", ".xml",
    ".sh", ".bash", ".ps1", ".bat", ".cmd",
    ".sql",
    ".env", ".env.example",
    ".gitignore", ".dockerignore",
    "Dockerfile", "Makefile",
    ".lock"
)

$ChangesLog = @()

function Write-Log {
    param([string]$Message, [string]$Type = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Type] $Message"
    Write-Host $logEntry -ForegroundColor $(switch ($Type) {
        "INFO" { "Cyan" }
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        "DRYRUN" { "Magenta" }
        default { "White" }
    })
    return $logEntry
}

function Should-Exclude {
    param([string]$Path)
    
    foreach ($exclude in $ExcludeFolders) {
        if ($Path -match [regex]::Escape("\$exclude\") -or $Path -match [regex]::Escape("/$exclude/")) {
            return $true
        }
        # Check if the path ends with the excluded folder
        if ($Path -match [regex]::Escape("\$exclude") + "$" -or $Path -match [regex]::Escape("/$exclude") + "$") {
            return $true
        }
    }
    return $false
}

function Is-TextFile {
    param([string]$FilePath)
    
    $fileName = Split-Path $FilePath -Leaf
    $extension = [System.IO.Path]::GetExtension($FilePath).ToLower()
    
    # Check extension
    if ($TextFileExtensions -contains $extension) {
        return $true
    }
    
    # Check specific filenames without extensions
    $specialFiles = @("Dockerfile", "Makefile", "LICENSE", "README", "CHANGELOG", "AUTHORS", "CONTRIBUTORS")
    if ($specialFiles -contains $fileName) {
        return $true
    }
    
    return $false
}

function Replace-InFileContent {
    param([string]$FilePath)
    
    if (Should-Exclude $FilePath) {
        return $false
    }
    
    if (-not (Is-TextFile $FilePath)) {
        return $false
    }
    
    try {
        $content = Get-Content $FilePath -Raw -ErrorAction Stop
        if ($null -eq $content) {
            return $false
        }
        
        $originalContent = $content
        
        # Replace all variations
        $content = $content -creplace $OldNameUpper, $NewNameUpper
        $content = $content -creplace $OldNameCamel, $NewNameCamel
        $content = $content -creplace $OldName, $NewName
        
        if ($content -ne $originalContent) {
            if ($DryRun) {
                $script:ChangesLog += Write-Log "Would replace content in: $FilePath" "DRYRUN"
            } else {
                Set-Content -Path $FilePath -Value $content -NoNewline -ErrorAction Stop
                $script:ChangesLog += Write-Log "Replaced content in: $FilePath" "SUCCESS"
            }
            return $true
        }
    }
    catch {
        $script:ChangesLog += Write-Log "Error processing file $FilePath : $_" "ERROR"
    }
    
    return $false
}

function Rename-ItemSafely {
    param(
        [string]$Path,
        [string]$NewName
    )
    
    if (Should-Exclude $Path) {
        return $null
    }
    
    $parent = Split-Path $Path -Parent
    $newPath = Join-Path $parent $NewName
    
    if ($DryRun) {
        $script:ChangesLog += Write-Log "Would rename: $Path -> $newPath" "DRYRUN"
        return $newPath
    } else {
        try {
            Rename-Item -Path $Path -NewName $NewName -ErrorAction Stop
            $script:ChangesLog += Write-Log "Renamed: $Path -> $newPath" "SUCCESS"
            return $newPath
        }
        catch {
            $script:ChangesLog += Write-Log "Error renaming $Path : $_" "ERROR"
            return $null
        }
    }
}

# Main execution
Write-Log "=============================================="
Write-Log "Agentcore to Agentcore Rename Script"
Write-Log "=============================================="
Write-Log "Root Path: $RootPath"
Write-Log "Dry Run: $DryRun"
Write-Log "Excluding folders: $($ExcludeFolders -join ', ')"
Write-Log "=============================================="

if (-not (Test-Path $RootPath)) {
    Write-Log "Root path does not exist: $RootPath" "ERROR"
    exit 1
}

# Phase 1: Replace content in files
Write-Log ""
Write-Log "Phase 1: Replacing content in files..." "INFO"
Write-Log "----------------------------------------------"

$allFiles = Get-ChildItem -Path $RootPath -Recurse -File -ErrorAction SilentlyContinue | 
    Where-Object { -not (Should-Exclude $_.FullName) }

$contentChangedCount = 0
foreach ($file in $allFiles) {
    if (Replace-InFileContent $file.FullName) {
        $contentChangedCount++
    }
}
Write-Log "Files with content changes: $contentChangedCount" "INFO"

# Phase 2: Rename files containing 'agentcore'
Write-Log ""
Write-Log "Phase 2: Renaming files..." "INFO"
Write-Log "----------------------------------------------"

$filesToRename = Get-ChildItem -Path $RootPath -Recurse -File -ErrorAction SilentlyContinue | 
    Where-Object { 
        ($_.Name -match $OldName -or $_.Name -match $OldNameCamel -or $_.Name -match $OldNameUpper) -and
        -not (Should-Exclude $_.FullName)
    } |
    Sort-Object { $_.FullName.Length } -Descending

$filesRenamedCount = 0
foreach ($file in $filesToRename) {
    $newFileName = $file.Name -creplace $OldNameUpper, $NewNameUpper
    $newFileName = $newFileName -creplace $OldNameCamel, $NewNameCamel
    $newFileName = $newFileName -creplace $OldName, $NewName
    
    if ($newFileName -ne $file.Name) {
        $result = Rename-ItemSafely -Path $file.FullName -NewName $newFileName
        if ($null -ne $result) {
            $filesRenamedCount++
        }
    }
}
Write-Log "Files renamed: $filesRenamedCount" "INFO"

# Phase 3: Rename folders containing 'agentcore' (deepest first)
Write-Log ""
Write-Log "Phase 3: Renaming folders..." "INFO"
Write-Log "----------------------------------------------"

$foldersToRename = Get-ChildItem -Path $RootPath -Recurse -Directory -ErrorAction SilentlyContinue | 
    Where-Object { 
        ($_.Name -match $OldName -or $_.Name -match $OldNameCamel -or $_.Name -match $OldNameUpper) -and
        -not (Should-Exclude $_.FullName)
    } |
    Sort-Object { $_.FullName.Length } -Descending

$foldersRenamedCount = 0
foreach ($folder in $foldersToRename) {
    # Re-check if folder still exists (parent might have been renamed)
    if (-not $DryRun -and -not (Test-Path $folder.FullName)) {
        continue
    }
    
    $newFolderName = $folder.Name -creplace $OldNameUpper, $NewNameUpper
    $newFolderName = $newFolderName -creplace $OldNameCamel, $NewNameCamel
    $newFolderName = $newFolderName -creplace $OldName, $NewName
    
    if ($newFolderName -ne $folder.Name) {
        $result = Rename-ItemSafely -Path $folder.FullName -NewName $newFolderName
        if ($null -ne $result) {
            $foldersRenamedCount++
        }
    }
}
Write-Log "Folders renamed: $foldersRenamedCount" "INFO"

# Summary
Write-Log ""
Write-Log "=============================================="
Write-Log "SUMMARY" "INFO"
Write-Log "=============================================="
Write-Log "Files with content changes: $contentChangedCount"
Write-Log "Files renamed: $filesRenamedCount"
Write-Log "Folders renamed: $foldersRenamedCount"
Write-Log "Total changes: $($contentChangedCount + $filesRenamedCount + $foldersRenamedCount)"

if ($DryRun) {
    Write-Log ""
    Write-Log "This was a DRY RUN. No actual changes were made." "WARNING"
    Write-Log "Run without -DryRun to apply changes." "WARNING"
}

# Save log to file
$logFile = Join-Path $RootPath "rename_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$ChangesLog | Out-File -FilePath $logFile -Encoding UTF8
Write-Log ""
Write-Log "Log saved to: $logFile" "INFO"

Write-Log ""
Write-Log "Script completed!" "SUCCESS"
