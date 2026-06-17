#!/usr/bin/env bash
#
# 운영 서버 systemd 설치/갱신 스크립트.
#
# 사용 예:
#   sudo bash scripts/install_systemd.sh --reset-seed-operational
#   sudo APP_USER=workshop APP_DIR=/opt/workshop_be bash scripts/install_systemd.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_USER="${APP_USER:-$(id -un "${SUDO_UID:-$(id -u)}")}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
RESET_SEED_OPERATIONAL=0

usage() {
  cat <<'EOF'
Usage:
  sudo bash scripts/install_systemd.sh [options]

Options:
  --reset-seed-operational  Reset DB and insert operational seed data once before starting.
  -h, --help                Show this help.

Environment overrides:
  APP_DIR                   Project directory. Default: current repository root
  APP_USER                  User to run services as. Default: sudo caller/current user
  APP_GROUP                 Group to run services as. Default: APP_USER
  VENV_DIR                  Python virtualenv path. Default: APP_DIR/venv
  BACKEND_HOST              Backend bind host. Default: 0.0.0.0
  BACKEND_PORT              Backend port. Default: 8000
  FRONTEND_HOST             Frontend bind host. Default: 0.0.0.0
  FRONTEND_PORT             Frontend port. Default: 5173
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset-seed-operational)
      RESET_SEED_OPERATIONAL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "systemd unit 설치는 root 권한이 필요합니다. sudo로 실행하세요." >&2
  exit 1
fi

PYTHON_BIN="$VENV_DIR/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "가상환경 python을 찾을 수 없습니다: $PYTHON_BIN" >&2
  echo "먼저 venv를 만들고 의존성을 설치하세요." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo ".env 파일을 찾을 수 없습니다: $APP_DIR/.env" >&2
  exit 1
fi

if [[ ! -d "$APP_DIR/frontend/node_modules" ]]; then
  echo "frontend/node_modules가 없습니다. frontend에서 npm install을 먼저 실행하세요." >&2
  exit 1
fi

echo "[build] frontend"
(
  cd "$APP_DIR/frontend"
  npm run build
)

echo "[db] alembic upgrade head"
(
  cd "$APP_DIR"
  "$PYTHON_BIN" -m alembic upgrade head
)

if [[ "$RESET_SEED_OPERATIONAL" -eq 1 ]]; then
  echo "[db] reset-seed-operational"
  (
    cd "$APP_DIR"
    "$PYTHON_BIN" -m scripts.seed_db reset-seed-operational --yes
  )
fi

echo "[systemd] writing units"
cat > /etc/systemd/system/workshop-backend.service <<EOF
[Unit]
Description=Workshop Backend API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$PYTHON_BIN -m uvicorn app.main:app --host $BACKEND_HOST --port $BACKEND_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/workshop-frontend.service <<EOF
[Unit]
Description=Workshop Frontend Preview Server
After=network-online.target workshop-backend.service
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR/frontend
ExecStart=/usr/bin/env npm run preview -- --host $FRONTEND_HOST --port $FRONTEND_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable workshop-backend.service workshop-frontend.service
systemctl restart workshop-backend.service workshop-frontend.service

echo
echo "✅ systemd 서비스 설치/재시작 완료"
echo "   backend : http://$BACKEND_HOST:$BACKEND_PORT"
echo "   frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo
echo "상태 확인:"
echo "   systemctl status workshop-backend"
echo "   systemctl status workshop-frontend"
