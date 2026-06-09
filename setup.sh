#!/usr/bin/env bash
# =============================================================================
# HyperSpace-AGI v5.9 - Setup Script (macOS / Linux)
# =============================================================================
set -euo pipefail

# --- Colori ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# --- Banner ---
echo -e ""
echo -e "${CYAN}${BOLD}"
echo -e " ██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗ "
echo -e " ██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗"
echo -e " ███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝"
echo -e " ██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗"
echo -e " ██║  ██║   ██║   ██║     ███████╗██║  ██║"
echo -e " ╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝"
echo -e "  ███████╗██████╗  █████╗  ██████╗ ███████╗"
echo -e "  ██╔════╝██╔══██╗██╔══██╗██╔════╝ ██╔════╝"
echo -e "  ███████╗██████╔╝███████║██║  ███╗█████╗  "
echo -e "  ╚════██║██╔═══╝ ██╔══██║██║   ██║██╔══╝  "
echo -e "  ███████║██║     ██║  ██║╚██████╔╝███████╗"
echo -e "  ╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝${NC}"
echo -e "  ${BOLD}v5.9 — Distributed AI Agent Swarm${NC}"
echo -e ""

# --- Funzioni utility ---
step() { echo -e "\n${BLUE}${BOLD}[STEP $1]${NC} $2"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

spinner() {
    local pid=$1 msg=$2
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}${spin:$i:1}${NC}  %s" "$msg"
        i=$(( (i+1) % 10 ))
        sleep 0.1
    done
    printf "\r  ${GREEN}✓${NC}  %-50s\n" "$msg"
}

wait_healthy() {
    local name=$1 url=$2 max=${3:-60}
    local i=0
    printf "  ${CYAN}⠋${NC}  Attendo $name"
    while ! curl -sf "$url" > /dev/null 2>&1; do
        sleep 2; i=$((i+2))
        local pct=$(( i * 100 / max ))
        local bar=$(printf '%0.s█' $(seq 1 $((pct/5))))
        local empty=$(printf '%0.s░' $(seq 1 $((20-pct/5))))
        printf "\r  ${CYAN}⠋${NC}  %-20s [${GREEN}%s${NC}%s] %3d%%" "$name" "$bar" "$empty" "$pct"
        if [ $i -ge $max ]; then
            echo ""
            warn "$name non risponde dopo ${max}s - continuo comunque"
            return 1
        fi
    done
    printf "\r  ${GREEN}✓${NC}  %-20s [${GREEN}████████████████████${NC}] 100%%\n" "$name"
    return 0
}

pull_model() {
    local model=$1
    echo -e "  ${CYAN}⬇${NC}  Pull modello: ${BOLD}$model${NC}"
    # Pull con progress via API Ollama streaming
    local total=0 completed=0
    while IFS= read -r line; do
        local status=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || echo '')
        local tot=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo '0')
        local comp=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('completed',0))" 2>/dev/null || echo '0')
        if [ "$tot" -gt 0 ] 2>/dev/null; then
            local pct=$(( comp * 100 / tot ))
            local bar=$(printf '%0.s█' $(seq 1 $((pct/5 > 0 ? pct/5 : 1))))
            local empty=$(printf '%0.s░' $(seq 1 $((20 - pct/5))))
            local mb=$(( comp / 1048576 ))
            local total_mb=$(( tot / 1048576 ))
            printf "\r    [${GREEN}%-20s${NC}] %3d%% (%d/%d MB) %s" "$bar" "$pct" "$mb" "$total_mb" "$status"
        elif [ -n "$status" ]; then
            printf "\r    %-60s" "$status"
        fi
        if echo "$line" | grep -q '"status":"success"'; then
            printf "\n  ${GREEN}✓${NC}  $model pronto!\n"
            return 0
        fi
    done < <(curl -s -N -X POST http://localhost:11434/api/pull \
        -H 'Content-Type: application/json' \
        -d "{\"name\":\"$model\"}")
}

# =============================================================================
# STEP 1 - Prerequisiti
# =============================================================================
step 1 "Verifica prerequisiti"

command -v docker   >/dev/null 2>&1 && ok "Docker trovato: $(docker --version | cut -d' ' -f3 | tr -d ',')" || fail "Docker non installato. Scarica da https://docs.docker.com/get-docker/"
command -v python3  >/dev/null 2>&1 && ok "Python3 trovato" || fail "Python3 non trovato"
docker info         >/dev/null 2>&1 && ok "Docker daemon attivo" || fail "Docker non in esecuzione. Avvia Docker Desktop."

# Rileva OS
OS=$(uname -s)
case $OS in
  Darwin) ok "macOS rilevato ($(sw_vers -productVersion))" ;;
  Linux)  ok "Linux rilevato ($(uname -r))" ;;
  *)      warn "OS non riconosciuto: $OS" ;;
esac

# =============================================================================
# STEP 2 - Pulizia container esistenti
# =============================================================================
step 2 "Pulizia container precedenti"

if docker compose ps -q 2>/dev/null | grep -q .; then
    warn "Container esistenti trovati, li fermo..."
    docker compose down --remove-orphans 2>/dev/null &
    spinner $! "Fermando container..."
else
    ok "Nessun container attivo"
fi

# =============================================================================
# STEP 3 - Build immagini
# =============================================================================
step 3 "Build immagini Docker"
echo -e "  ${YELLOW}Questo può richiedere 3-5 minuti al primo avvio...${NC}"

docker compose build --progress=plain 2>&1 | while IFS= read -r line; do
    if echo "$line" | grep -qE '^#[0-9]+ '; then
        svc=$(echo "$line" | grep -oE '\[.*\]' | head -1 || echo '')
        printf "\r  ${CYAN}⠋${NC}  Building... %-40s" "$svc"
    fi
done
echo -e "\n  ${GREEN}✓${NC}  Build completata"

# =============================================================================
# STEP 4 - Avvio servizi
# =============================================================================
step 4 "Avvio stack HyperSpace-AGI"

docker compose up -d 2>/dev/null &
spinner $! "Avviando container..."

# =============================================================================
# STEP 5 - Health checks
# =============================================================================
step 5 "Attendo che i servizi siano healthy"
echo ""

wait_healthy "Ollama"         "http://localhost:11434/api/tags"  90
wait_healthy "Authority"      "http://localhost:8766/health"      60
wait_healthy "Node"           "http://localhost:8765/health"      60
wait_healthy "Worker"         "http://localhost:8767/health"      60
wait_healthy "Control-Plane" "http://localhost:8768/health"      60
wait_healthy "Open WebUI"    "http://localhost:8080"              120

# =============================================================================
# STEP 6 - Pull modello default
# =============================================================================
step 6 "Pull modello AI default (qwen3.5:7b ~4.7GB)"

# Controlla se già presente
if curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; models=[m['name'] for m in json.load(sys.stdin).get('models',[])]; exit(0 if any('qwen3.5' in m for m in models) else 1)" 2>/dev/null; then
    ok "qwen3.5:7b già presente, skip pull"
else
    warn "Prima installazione: scarico qwen3.5:7b (~4.7GB)..."
    pull_model "qwen3.5:7b"
fi

# =============================================================================
# DONE
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║       HyperSpace-AGI v5.9 è operativo! 🚀                ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║${NC}  🌐 Open WebUI      →  http://localhost:8080              ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}  🧠 Control Plane   →  http://localhost:8768             ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}  🔍 Authority       →  http://localhost:8766/catalog      ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}  🤖 Ollama API      →  http://localhost:11434/api/tags    ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║${NC}  Per fermare:  docker compose down                        ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}║${NC}  Per i log:    docker compose logs -f                     ${GREEN}${BOLD}║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Apri browser automaticamente
if [ "$OS" = "Darwin" ]; then
    open http://localhost:8080 2>/dev/null || true
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:8080 2>/dev/null || true
fi
