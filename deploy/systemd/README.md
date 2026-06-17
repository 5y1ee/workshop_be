# systemd 운영 배포

운영 서버에서는 개발용 `run_dev.sh` 대신 systemd 서비스를 사용한다.

## 최초 설치/갱신

```bash
sudo bash scripts/install_systemd.sh --reset-seed-operational
```

`--reset-seed-operational`은 DB를 초기화하므로 최초 운영 데이터 생성 때만 사용한다.
코드만 갱신해서 재배포할 때는 옵션 없이 실행한다.

```bash
sudo bash scripts/install_systemd.sh
```

## 서비스 제어

```bash
sudo systemctl status workshop-backend
sudo systemctl status workshop-frontend

sudo systemctl restart workshop-backend
sudo systemctl restart workshop-frontend

sudo journalctl -u workshop-backend -f
sudo journalctl -u workshop-frontend -f
```

기본 포트는 백엔드 `8000`, 프론트 `5173`이다.
