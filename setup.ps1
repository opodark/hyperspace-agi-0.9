# =============================================================================
# HyperSpace-AGI v5.9 - Setup Script (Windows PowerShell)
# =============================================================================
#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

# --- Colori e utility ---
function Write-Step   { param($n,$msg) Write-Host "`n[STEP $n] $msg" -ForegroundColor Cyan -NoNewline; Write-Host "" }
function Write-Ok     { param($msg)    Write-Host "  v  $msg" -ForegroundColor Green }
function Write-Warn   { param($msg)    Write-Host "  !  $msg" -ForegroundColor Yellow }
function Write-Fail   { param($msg)    Write-Host "  x  $msg" -ForegroundColor Red; exit 1 }

function Show-Spinner {
    param($ScriptBlock, $Message)
    $job = Start-Job -ScriptBlock $ScriptBlock
    $spin = @('|','/','-','\')
    $i = 0
    while ($job.State -eq 'Running') {
        Write-Host "`r  $($spin[$i % 4])  $Message" -NoNewline
        Start-Sleep -Milliseconds 100
        $i++
    }
    Receive-Job $job | Out-Null
    Remove-Job $job
    Write-Host "`r  v  $Message" -ForegroundColor Green
}

function Wait-Healthy {
    param($Name, $Url, $MaxSeconds = 60)
    $i = 0
    Write-Host "  -  Attendo $Name..." -NoNewline
    while ($i -lt $MaxSeconds) {
        try {
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($r.StatusCode -eq 200) {
                $bar = '#' * 20
                Write-Host "`r  v  $Name [$bar] 100%" -ForegroundColor Green
                return $true
            }
        } catch {}
        $pct = [int]($i * 100 / $MaxSeconds)
        $filled = [int]($pct / 5)
        $bar = ('#' * $filled).PadRight(20, '.')
        Write-Host "`r  -  $Name [$bar] $pct%" -NoNewline
        Start-Sleep -Seconds 2
        $i += 2
    }
    Write-Warn "$Name non risponde dopo ${MaxSeconds}s"
    return $false
}

function Pull-Model {
    param($ModelName)
    Write-Host "  >  Pull modello: $ModelName" -ForegroundColor Cyan
    $body = "{`"name`":`"$ModelName`"}"
    $req = [System.Net.HttpWebRequest]::Create('http://localhost:11434/api/pull')
    $req.Method = 'POST'
    $req.ContentType = 'application/json'
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $req.ContentLength = $bytes.Length
    $stream = $req.GetRequestStream()
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()
    $resp = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        try {
            $obj = $line | ConvertFrom-Json
            if ($obj.total -gt 0) {
                $pct = [int]($obj.completed * 100 / $obj.total)
                $filled = [int]($pct / 5)
                $bar = ('#' * $filled).PadRight(20, '.')
                $mb = [int]($obj.completed / 1MB)
                $tot = [int]($obj.total / 1MB)
                Write-Host "`r    [$bar] $pct% ($mb/$tot MB)" -NoNewline
            } elseif ($obj.status) {
                Write-Host "`r    $($obj.status.PadRight(60))" -NoNewline
            }
            if ($obj.status -eq 'success') {
                Write-Host ""
                Write-Ok "$ModelName pronto!"
                return
            }
        } catch {}
    }
}

# --- Banner ---
Write-Host ""
Write-Host "  HyperSpace-AGI v5.9" -ForegroundColor Cyan
Write-Host "  Distributed AI Agent Swarm" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
Write-Step 1 "Verifica prerequisiti"
# =============================================================================

try   { $v = (docker --version); Write-Ok "Docker: $v" }
catch { Write-Fail "Docker non installato. Scarica da https://docs.docker.com/get-docker/" }

try   { docker info | Out-Null; Write-Ok "Docker daemon attivo" }
catch { Write-Fail "Docker non in esecuzione. Avvia Docker Desktop." }

try   { python --version | Out-Null; Write-Ok "Python trovato" }
catch { Write-Warn "Python non trovato - alcune feature potrebbero non funzionare" }

Write-Ok "Windows $(([System.Environment]::OSVersion.Version).ToString())"

# =============================================================================
Write-Step 2 "Pulizia container precedenti"
# =============================================================================

$running = docker compose ps -q 2>$null
if ($running) {
    Write-Warn "Container esistenti trovati, li fermo..."
    Show-Spinner { docker compose down --remove-orphans 2>$null } "Fermando container..."
} else {
    Write-Ok "Nessun container attivo"
}

# =============================================================================
Write-Step 3 "Build immagini Docker"
# =============================================================================

Write-Warn "Questo puo' richiedere 3-5 minuti al primo avvio..."
Show-Spinner { docker compose build 2>$null } "Building immagini..."

# =============================================================================
Write-Step 4 "Avvio stack HyperSpace-AGI"
# =============================================================================

Show-Spinner { docker compose up -d 2>$null } "Avviando container..."

# =============================================================================
Write-Step 5 "Attendo health checks"
# =============================================================================

Write-Host ""
Wait-Healthy "Ollama"        "http://localhost:11434/api/tags"  90
Wait-Healthy "Authority"     "http://localhost:8766/health"      60
Wait-Healthy "Node"          "http://localhost:8765/health"      60
Wait-Healthy "Worker"        "http://localhost:8767/health"      60
Wait-Healthy "Control-Plane" "http://localhost:8768/health"      60
Wait-Healthy "Open WebUI"    "http://localhost:8080"             120

# =============================================================================
Write-Step 6 "Pull modello AI default (qwen3.5:7b ~4.7GB)"
# =============================================================================

$tags = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -UseBasicParsing
$hasModel = $tags.models | Where-Object { $_.name -like '*qwen3.5*' }
if ($hasModel) {
    Write-Ok "qwen3.5:7b gia' presente, skip pull"
} else {
    Write-Warn "Prima installazione: scarico qwen3.5:7b (~4.7GB)..."
    Pull-Model "qwen3.5:7b"
}

# =============================================================================
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  HyperSpace-AGI v5.9 e' operativo!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  Open WebUI    ->  http://localhost:8080"
Write-Host "  Control Plane ->  http://localhost:8768"
Write-Host "  Authority     ->  http://localhost:8766/catalog"
Write-Host "  Ollama API    ->  http://localhost:11434/api/tags"
Write-Host "----------------------------------------------------------------" -ForegroundColor Green
Write-Host "  Per fermare:  docker compose down"
Write-Host "  Per i log:    docker compose logs -f"
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://localhost:8080"
