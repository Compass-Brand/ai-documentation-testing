# Setup script for AI Documentation Testing (Windows PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"

function Write-Info  { Write-Host "[INFO] $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "[ERROR] $args" -ForegroundColor Red }

# Navigate to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir
Write-Info "Project directory: $ProjectDir"

# --- Check Python ---
Write-Info "Checking Python..."
$Python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $version = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($version) {
            $Python = $cmd
            break
        }
    } catch { }
}

if (-not $Python) {
    Write-Err "Python not found. Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
}

$PyMajor = & $Python -c "import sys; print(sys.version_info.major)"
$PyMinor = & $Python -c "import sys; print(sys.version_info.minor)"
$PyVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

if ([int]$PyMajor -lt 3 -or ([int]$PyMajor -eq 3 -and [int]$PyMinor -lt 11)) {
    Write-Err "Python 3.11+ required (found $PyVersion)"
    exit 1
}
Write-Info "Python $PyVersion found"

# --- Check/Install UV ---
Write-Info "Checking UV package manager..."
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvPath) {
    Write-Warn "UV not found. Installing..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } catch {
        Write-Err "UV installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }

    $uvPath = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvPath) {
        Write-Err "UV not found after install. Restart your terminal and try again."
        exit 1
    }
}
$uvVersion = & uv --version
Write-Info "UV $uvVersion found"

# --- Install dependencies ---
Write-Info "Installing project dependencies..."
& uv sync --dev --all-packages
if ($LASTEXITCODE -ne 0) {
    Write-Err "Dependency installation failed"
    exit 1
}
Write-Info "Dependencies installed"

# --- Setup .env ---
if (-not (Test-Path .env)) {
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Warn "Created .env from .env.example"
        Write-Warn "Edit .env and add your OPENROUTER_API_KEY from https://openrouter.ai/keys"
    } else {
        Write-Warn "No .env.example found. Create .env with: OPENROUTER_API_KEY=sk-or-v1-your-key"
    }
} else {
    Write-Info ".env already exists"
}

# --- Verify installation ---
Write-Info "Running tests to verify installation..."
& uv run python -m pytest --tb=short -q
if ($LASTEXITCODE -eq 0) {
    Write-Info "All tests passed"
} else {
    Write-Warn "Some tests failed. Check output above."
}

# --- Verify CLI tools ---
Write-Info "Verifying CLI tools..."
try {
    & uv run agent-evals --help 2>$null | Out-Null
    Write-Info "agent-evals CLI available"
} catch {
    Write-Warn "agent-evals CLI not found. Try: uv run agent-evals --help"
}

try {
    & uv run agent-index --help 2>$null | Out-Null
    Write-Info "agent-index CLI available"
} catch {
    Write-Warn "agent-index CLI not found. Try: uv run agent-index --help"
}

Write-Host ""
Write-Info "Setup complete!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit .env with your OPENROUTER_API_KEY"
Write-Host "  2. Run a dry-run:  uv run agent-evals --model openrouter/anthropic/claude-sonnet-4.5 --dry-run"
Write-Host "  3. Run tests:      uv run python -m pytest"
Write-Host "  4. Run evals:      uv run agent-evals --config agent-evals\examples\minimal-config.yaml"
