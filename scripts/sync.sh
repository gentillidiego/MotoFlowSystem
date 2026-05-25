#!/bin/bash
# =============================================================================
# sync.sh — Commit e push rápido para o MotoFlowSystem
# Uso: ./scripts/sync.sh "mensagem do commit"
#      ./scripts/sync.sh              (usa timestamp automático)
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Mensagem do commit
if [ -n "$1" ]; then
    MSG="$1"
else
    MSG="chore: sync automático $(date '+%d/%m/%Y %H:%M')"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄  MotoFlow — Git Sync"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verifica se há algo para commitar
if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "✅  Nada a commitar. Repositório limpo."
    exit 0
fi

echo "📁  Arquivos modificados:"
git status --short
echo ""

git add .
git commit -m "$MSG"
git push origin main

echo ""
echo "✅  Push realizado com sucesso!"
echo "🔗  https://github.com/gentillidiego/MotoFlowSystem"
