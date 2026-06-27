# ============================================================
#  WAL 小说写作 Agent — PowerShell 启动脚本
#
#  用法:
#    .\start.ps1                    # 交互选择项目
#    .\start.ps1 修仙传奇            # 直接打开指定项目
#    .\start.ps1 修仙传奇 --model deepseek-reasoner  # 指定模型
# ============================================================

param(
    [string]$ProjectName = "",
    [string]$Model = "deepseek-chat",
    [string]$BaseUrl = "https://api.deepseek.com/v1",
    [switch]$Quiet,
    [ValidateSet("writing", "planning", "autonomous")]
    [string]$Mode = "writing",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# ---- 终端能力检测 + 蓝底修复 ----
function Test-EmojiSupport {
    # Windows Terminal → 完美支持 Emoji
    if ($env:WT_SESSION) { return $true }
    # VSCode / Cursor / modern terminals
    if ($env:TERM_PROGRAM) { return $true }
    # 老 conhost (Win10 blue background) → Emoji 显示差
    return $false
}

# 修复 Win10 蓝底看不清
try {
    $bg = $Host.UI.RawUI.BackgroundColor
    if ($bg -eq [ConsoleColor]::DarkBlue -or $bg -eq [ConsoleColor]::Blue) {
        $Host.UI.RawUI.BackgroundColor = "Black"
        $Host.UI.RawUI.ForegroundColor = "White"
        Clear-Host
    }
} catch {
    # VSCode/ISE 等环境下 RawUI 不可用，忽略
}

# 传递 emoji 检测结果给 Python
if (-not (Test-EmojiSupport)) {
    $env:WAL_NO_EMOJI = "1"
}

# ---- 帮助 ----
if ($Help) {
    Write-Host @"
WAL 小说写作 Agent 启动器

用法:
  .\start.ps1 [项目名] [选项]

参数:
  -ProjectName    小说项目名（不填则交互选择）
  -Model          LLM 模型 (默认: deepseek-chat)
  -BaseUrl        API 地址 (默认: https://api.deepseek.com/v1)
  -Quiet          安静模式启动（隐藏工具调用详情）
  -Mode           Agent 启动模式: writing / planning / autonomous (默认: writing)
  -Help           显示此帮助

前置条件:
  1. 设置环境变量 DEEPSEEK_API_KEY
     或在项目目录下创建 .env 文件: DEEPSEEK_API_KEY=sk-xxx

  2. 如果没有项目，先运行:
     & d:\PyVenv\WAL\Scripts\python.exe -m wal.cli.main init 我的小说 --author "作者" --summary "简介" --genre "类型"

示例:
  .\start.ps1                       # 交互选择项目
  .\start.ps1 修仙传奇               # 启动修仙传奇项目
  .\start.ps1 修仙传奇 -Model deepseek-reasoner  # 使用推理模型
  .\start.ps1 修仙传奇 -Quiet        # 安静模式启动
  .\start.ps1 修仙传奇 -Mode planning # 以规划模式启动
  .\start.ps1 修仙传奇 -Mode autonomous -Quiet  # 自主+安静模式
"@
    exit 0
}

# ---- 基础路径 ----
$scriptDir = $PSScriptRoot
$env:PYTHONPATH = $scriptDir
$env:WAL_PROJECTS = Join-Path $scriptDir "projects"

# ---- 加载 .env 文件（必须在激活 venv 之前，让 WAL_VENV 生效）----
$envFile = Join-Path $scriptDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            if ($key -and $value) {
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
}

# ---- 激活虚拟环境 ----
$venvRoot = if ($env:WAL_VENV) {
    $env:WAL_VENV
} elseif (Test-Path (Join-Path $scriptDir ".venv\Scripts\Activate.ps1")) {
    Join-Path $scriptDir ".venv"
} else {
    "d:\PyVenv\WAL"
}
$venvActivate = Join-Path $venvRoot "Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "[WAL] Activating virtual environment..." -ForegroundColor Cyan
    & $venvActivate
} else {
    Write-Host "[WAL] WARNING: Virtual environment not found at $venvActivate" -ForegroundColor Yellow
}

# ---- 检查 API Key ----
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "[WAL] DEEPSEEK_API_KEY not set!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please set your DeepSeek API key:" -ForegroundColor Yellow
    Write-Host "    1. Create a .env file in project root: " -NoNewline
    Write-Host (Join-Path $scriptDir ".env") -ForegroundColor White
    Write-Host '    2. Add line: DEEPSEEK_API_KEY=sk-your-key-here' -ForegroundColor White
    Write-Host "    3. Or set environment variable: " -NoNewline
    Write-Host '$env:DEEPSEEK_API_KEY = "sk-..."' -ForegroundColor White
    Write-Host ""
    $apiKey = Read-Host "  Or enter API key now (not saved)"
    if ($apiKey) {
        $env:DEEPSEEK_API_KEY = $apiKey
    } else {
        Write-Host "[WAL] Cannot start without API key." -ForegroundColor Red
        exit 1
    }
}

# ---- 交互选择项目 ----
if (-not $ProjectName) {
    $projectsDir = $env:WAL_PROJECTS
    if (-not (Test-Path $projectsDir)) {
        Write-Host "[WAL] No projects directory found. Creating one..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path $projectsDir | Out-Null
    }

    # 用 .NET 方法获取目录名，避免 Select-Object -ExpandProperty 在某些环境截断 Unicode
    $projects = @([System.IO.Directory]::GetDirectories($projectsDir) | ForEach-Object { [System.IO.Path]::GetFileName($_) })

    if (-not $projects -or $projects.Count -eq 0) {
        Write-Host "[WAL] No projects found!" -ForegroundColor Yellow
        Write-Host "  Projects dir: $projectsDir" -ForegroundColor Gray
        Write-Host ""

        $createNew = Read-Host "  Create a new project? Enter name (or press Enter to exit)"
        if (-not $createNew) { exit 0 }

        $ProjectName = $createNew

        # 选类型
        Write-Host ""
        Write-Host "  选择类型/流派：" -ForegroundColor White
        $genres = @("玄幻", "仙侠", "都市", "科幻", "历史", "悬疑", "言情", "武侠", "游戏", "轻小说", "General")
        for ($i = 0; $i -lt $genres.Count; $i++) {
            Write-Host "    $($i+1). $($genres[$i])"
        }
        $genreChoice = Read-Host "  输入编号 (默认 1=玄幻)"
        $genreIndex = 0
        if ($genreChoice -match '^\d+$') {
            $idx = [int]$genreChoice - 1
            if ($idx -ge 0 -and $idx -lt $genres.Count) { $genreIndex = $idx }
        }
        $genre = $genres[$genreIndex]

        # 作者名 + 简介
        $author = Read-Host "  作者笔名 (回车跳过)"
        if (-not $author) { $author = "佚名" }
        $summary = Read-Host "  一句话简介 (回车跳过)"
        if (-not $summary) { $summary = "新故事" }

        & (Join-Path $venvRoot "Scripts\python.exe") -m wal.cli.main init $ProjectName --author $author --summary $summary --genre $genre
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WAL] Failed to create project." -ForegroundColor Red
            exit 1
        }
    } else {
        # 始终显示项目列表让用户选择（即使是单个项目也确认一下）
        Write-Host "[WAL] Projects in $projectsDir`:" -ForegroundColor Cyan
        for ($i = 0; $i -lt $projects.Count; $i++) {
            Write-Host "  $($i+1). $($projects[$i])"
        }
        if ($projects.Count -eq 1) {
            $choice = Read-Host "  Press Enter to select '$($projects[0])', or type name to create new"
            if (-not $choice -or $choice -eq "1") {
                $ProjectName = $projects[0]
            } else {
                $ProjectName = $choice
                # 如果输入的不是已有项目名，创建新项目
                if ($choice -notin $projects) {
                    Write-Host "  创建新项目 '$choice'..." -ForegroundColor Yellow
                    & (Join-Path $venvRoot "Scripts\python.exe") -m wal.cli.main init $choice --author "佚名" --summary "新故事" --genre "General"
                    if ($LASTEXITCODE -ne 0) {
                        Write-Host "[WAL] Failed to create project." -ForegroundColor Red
                        exit 1
                    }
                }
            }
        } else {
            $choice = Read-Host "  Select (1-$($projects.Count)), or type name to create new"
            if ($choice -match '^\d+$') {
                $idx = [int]$choice - 1
                if ($idx -ge 0 -and $idx -lt $projects.Count) {
                    $ProjectName = $projects[$idx]
                } else {
                    Write-Host "[WAL] Invalid selection." -ForegroundColor Red
                    exit 1
                }
            } elseif ($choice) {
                $ProjectName = $choice
                if ($choice -notin $projects) {
                    Write-Host "  创建新项目 '$choice'..." -ForegroundColor Yellow
                    & (Join-Path $venvRoot "Scripts\python.exe") -m wal.cli.main init $choice --author "佚名" --summary "新故事" --genre "General"
                    if ($LASTEXITCODE -ne 0) {
                        Write-Host "[WAL] Failed to create project." -ForegroundColor Red
                        exit 1
                    }
                }
            } else {
                exit 0
            }
        }
    }
}

# ---- 启动 Agent ----
Write-Host "[WAL] Starting agent for project: $ProjectName" -ForegroundColor Green
Write-Host "[WAL] Model: $Model" -ForegroundColor Green
Write-Host ""

$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
$launcherScript = Join-Path $scriptDir "wal\agent\launch.py"

$launchArgs = @($launcherScript, $ProjectName, "--model", $Model, "--base-url", $BaseUrl, "--mode", $Mode)
if ($Quiet) {
    $launchArgs += "--quiet"
}

& $pythonExe $launchArgs
