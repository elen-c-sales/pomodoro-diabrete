#!/usr/bin/env bash
# Roda o Pomodoro Pet localmente.
#
# Uso:
#   ./run.sh            -> Docker (padrao): build da imagem + run com X11
#   ./run.sh --local    -> roda nativo numa venv (sem Docker)
#   ./run.sh --demo     -> repassa flags ao app (ex.: --demo, --opaque)
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=pomodoro-diabrete
ARGS=()
MODE=docker

for arg in "$@"; do
    if [[ "$arg" == "--local" ]]; then
        MODE=local
    else
        ARGS+=("$arg")
    fi
done

if [[ "$MODE" == local ]]; then
    if [[ ! -d .venv ]]; then
        python3 -m venv .venv
        .venv/bin/pip install -q -r requirements.txt
    fi
    exec .venv/bin/python pomodoro.py "${ARGS[@]}"
fi

docker build -q -t "$IMAGE" .

# Precisa de acesso ao X do host para abrir a janela do Pygame.
if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY nao definido; use ./run.sh --local ou rode dentro de uma sessao grafica." >&2
    exit 1
fi
# Libera so o usuario atual (o container roda com o mesmo UID) e revoga ao
# sair. Sem exec no docker run, senao o trap nao chega a rodar.
XUSER="SI:localuser:$(id -un)"
xhost "+$XUSER" >/dev/null 2>&1 || true
trap 'xhost "-$XUSER" >/dev/null 2>&1 || true' EXIT

DOCKER_ARGS=("$IMAGE")
if (( ${#ARGS[@]} )); then
    DOCKER_ARGS+=(python pomodoro.py --opaque "${ARGS[@]}")
fi

docker run --rm -it \
    --user "$(id -u):$(id -g)" \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    "${DOCKER_ARGS[@]}"
