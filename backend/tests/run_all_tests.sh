#!/bin/bash
# run_all_tests.sh
# Roda todas as suítes de teste do GateFlow em sequência. Cada arquivo usa
# seu próprio banco de dados de teste (apagado e recriado do zero antes de
# cada suíte), então a ordem de execução não importa e não há risco de um
# teste "sujar" o banco para o próximo.
#
# Uso:
#   cd backend
#   ./tests/run_all_tests.sh

set -e  # para no primeiro erro

cd "$(dirname "$0")/.."  # garante que roda a partir da pasta backend/

echo "=================================================================="
echo "GateFlow — Suíte de Testes Automatizados"
echo "=================================================================="

for test_file in tests/test_*.py; do
    echo ""
    echo "--- Rodando: $test_file ---"
    rm -rf data
    python3 "$test_file"
done

rm -rf data
echo ""
echo "=================================================================="
echo "TODAS AS SUÍTES PASSARAM"
echo "=================================================================="
