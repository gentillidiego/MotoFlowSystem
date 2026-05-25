#!/bin/bash
# =============================================================================
# watch.sh — Watcher automático: detecta mudanças e faz push
# Requer: inotify-tools  →  sudo apt install inotify-tools
#
# Uso:  ./scripts/watch.sh          (monitor + auto-commit a cada mudança)
#       ./scripts/watch.sh --delay 30  (aguarda 30s de inatividade antes de commitar)
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Parâmetros
DELAY=${2:-10}  # Segundos de inatividade antes de commitar (padrão: 10s)

# Pastas/arquivos a ignorar no monitoramento
IGNORE_DIRS="venv|.git|__pycache__|.pytest_cache|node_modules|.claude"

# Verifica dependência
if ! command -v inotifywait &>/dev/null; then
    echo ""
    echo "❌  inotify-tools não encontrado!"
    echo "    Instale com: sudo apt install inotify-tools"
    echo ""
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "👁️   MotoFlow — Auto-Watcher Ativo"
echo "📂  Monitorando: $PROJECT_DIR"
echo "⏱️   Delay antes do commit: ${DELAY}s de inatividade"
echo "🛑  Para parar: Ctrl+C"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Timer para debounce (evita múltiplos commits em sequência)
TIMER_PID=""

do_commit() {
    sleep "$DELAY"
    if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        return
    fi
    MSG="chore: auto-sync $(date '+%d/%m/%Y %H:%M:%S')"
    echo ""
    echo "📦  Commitando: $MSG"
    git add .
    git commit -m "$MSG" --quiet
    git push origin main --quiet
    echo "✅  Push feito! [$(date '+%H:%M:%S')]"
}

# Loop de monitoramento
while true; do
    # Aguarda qualquer evento de escrita/criação/remoção
    inotifywait -r -e modify,create,delete,move \
        --exclude "($IGNORE_DIRS)" \
        "$PROJECT_DIR" -q 2>/dev/null

    echo "🔔  Mudança detectada [$(date '+%H:%M:%S')]"

    # Cancela timer anterior (debounce)
    if [ -n "$TIMER_PID" ] && kill -0 "$TIMER_PID" 2>/dev/null; then
        kill "$TIMER_PID" 2>/dev/null || true
    fi

    # Agenda novo commit após DELAY segundos de inatividade
    do_commit &
    TIMER_PID=$!
done
