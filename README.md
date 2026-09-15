# 짜장면 vs 짬뽕 투표 API

한 사람이 한 번만 투표할 수 있고, 재시작해도 표가 남는 최소 운영형 백엔드입니다.

**현재 Public URL:** https://jjajang-vs-jjamppong.fly.dev

- Health: https://jjajang-vs-jjamppong.fly.dev/health
- Result: https://jjajang-vs-jjamppong.fly.dev/api/result
- Swagger: https://jjajang-vs-jjamppong.fly.dev/docs

전체 구조도는 [`ARCHITECTURE.html`](./ARCHITECTURE.html)을 브라우저로 열면 볼 수 있습니다.

---

## 1. 실행 방법

### 로컬 (Docker)

```bash
docker compose up --build -d
curl http://localhost:8080/health
```

Compose 없이 실행할 경우:

```bash
docker build -t backend-test .
docker run --name backend-test -p 8080:8080 -v votes-data:/data --restart unless-stopped backend-test
```

### 로컬 (Python)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
DATABASE_PATH=./votes.db .venv/bin/uvicorn app.main:app --port 8080
```

Windows PowerShell에서는 `.venv\Scripts\python -m uvicorn app.main:app --port 8080`을 사용합니다.

### API 호출

```bash
curl -X POST http://localhost:8080/api/vote \
  -H "Content-Type: application/json" \
  -d '{"choice":"jajang","voterId":"user-123"}'

curl http://localhost:8080/api/result
curl http://localhost:8080/health
```

| 엔드포인트 | 응답 |
| --- | --- |
| `GET /` | `200` 서비스 상태와 사용 가능한 엔드포인트 안내 |
| `POST /api/vote` | `201` 투표 완료 / `409` 이미 투표한 `voterId` / `422` `choice` 오류·`voterId` 누락 |
| `GET /api/result` | `200` `{"jajang":n,"jjamppong":n,"total":n}` |
| `GET /health` | `200` `{"status":"ok"}` (DB에 실제 질의 후 응답) |

### 테스트

```bash
.venv/bin/pytest -q
```

동시 투표 100건 유실 여부, 동일 `voterId` 20건 동시 요청 시 1건만 성공, 재시작 후 데이터·중복 규칙 유지를 검증합니다.

다른 사람의 Public URL을 빠르게 점검하려면:

```bash
python scripts/smoke_test.py https://상대방-public-url
```

Session 2 전체 기능·동시성·정합성 테스트를 본 서비스에 실행하려면:

```bash
python scripts/session2_test.py https://jjajang-vs-jjamppong.fly.dev
```

실제 수행 결과와 제출용 문안은 [`SESSION2_REPORT.md`](./SESSION2_REPORT.md)에 정리했습니다.

---

## 2. 사용한 기술

| 영역 | 선택 |
| --- | --- |
| 언어·런타임 | Python 3.12 |
| 웹 프레임워크 | FastAPI 0.116 (Pydantic 입력 검증, 자동 OpenAPI) |
| 서버 | Uvicorn 0.35, worker 1개 |
| 저장소 | SQLite (WAL 모드) |
| 패키징 | Docker (`python:3.12-slim`, non-root 실행) |
| 배포 | Fly.io 단일 Machine + Fly Volume (region `nrt`) |
| CI/CD | GitHub Actions — `main` push 시 테스트, Fly token 설정 시 자동 배포 |

의존성은 `fastapi`, `uvicorn[standard]` 두 개뿐입니다. smoke 스크립트는 표준 라이브러리만 사용합니다.

---

## 3. 데이터 저장 방식

SQLite 파일 하나(`/data/votes.db`)에 투표 1건을 1행으로 저장합니다.

```sql
CREATE TABLE IF NOT EXISTS votes (
    voter_id   TEXT PRIMARY KEY,
    choice     TEXT NOT NULL CHECK (choice IN ('jajang', 'jjamppong')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- 집계값을 따로 들고 있지 않습니다. `GET /api/result`는 조회 시점에 `COUNT(*) FILTER`로 한 번 스캔해 세 값을 계산합니다. 카운터와 원본이 어긋날 여지를 아예 만들지 않기 위해서입니다.
- DB 경로는 `create_app(database_path)` 인자 → 환경변수 `DATABASE_PATH` → 기본값 `/data/votes.db` 순으로 결정됩니다. 덕분에 테스트는 임시 디렉터리로 완전히 격리됩니다.
- 스키마 생성은 앱 기동 시 `lifespan`에서 `CREATE TABLE IF NOT EXISTS`로 수행하므로, 빈 볼륨에 처음 배포해도 별도 마이그레이션 단계가 필요 없습니다.

---

## 4. 동시성 및 중복 투표 처리 방식

**"먼저 조회해서 있으면 거절"을 하지 않습니다.** 조회와 삽입 사이에는 항상 경쟁 구간이 생기고, 그 틈에 같은 `voterId`가 두 번 들어갈 수 있기 때문입니다.

대신 곧바로 `INSERT`를 던지고, `voter_id`의 PRIMARY KEY 제약이 거부한 결과를 409로 번역합니다.

```python
try:
    connection.execute("INSERT INTO votes (voter_id, choice) VALUES (?, ?)", (voter_id, choice))
except sqlite3.IntegrityError as error:
    if "votes.voter_id" in str(error):
        raise HTTPException(status_code=409, detail="voterId has already voted")
```

유일성 판정이 애플리케이션이 아니라 DB 한 지점에서 원자적으로 끝나므로, 애플리케이션 레벨 락이 없어도 경쟁이 발생하지 않습니다.

동시 쓰기는 세 가지로 받아냅니다.

1. **WAL 저널** — 읽기가 쓰기를 막지 않아, 투표가 몰려도 `/api/result`가 대기하지 않습니다.
2. **`busy_timeout` 10초** — 쓰기 락이 겹칠 때 즉시 실패하는 대신 대기 후 재시도합니다.
3. **짧은 트랜잭션 + `workers=1`** — 트랜잭션이 단일 `INSERT`뿐이라 락 보유 시간이 최소이고, 단일 worker라 프로세스 간 쓰기 경합 자체가 없습니다.

검증 결과 (`tests/test_api.py`):

- 고유 `voterId` 100건을 20스레드로 동시 전송 → 100건 전부 `201`, 집계 유실 0건
- 동일 `voterId` 20건을 동시 전송 → 정확히 1건 `201`, 19건 `409`
- 전체 로컬 테스트 → `3 passed`

---

## 5. 재시작 후 데이터 유지 방식

DB 파일을 컨테이너 레이어가 아니라 **마운트된 영구 볼륨**에 둡니다. 컨테이너가 교체돼도 볼륨은 그대로 남습니다.

- 로컬: Docker named volume `votes-data` → `/data` (`compose.yaml`)
- 운영: Fly Volume `votes_data` → `/data` (`fly.toml`의 `[[mounts]]`)
- 두 환경 모두 `DATABASE_PATH=/data/votes.db`

배포로 Machine이 교체될 때도 같은 볼륨이 다시 붙으므로 기존 표가 유지됩니다.

이 동작은 테스트로도 고정해 두었습니다. 같은 DB 파일 경로로 FastAPI 애플리케이션을 두 번 생성해 프로세스 재시작을 모사하고, 재시작 후에도 이전 표가 남아 있으며 같은 `voterId`가 여전히 `409`로 거절되는지 확인합니다.

운영 환경에서도 Fly Machine을 실제 재시작해 확인했습니다. 재시작 전 `2표`가 재시작 후에도 그대로 유지됐고, 재시작 전 사용한 `voterId`는 이후 요청에서도 `409`로 거절됐습니다.

---

## 6. Public URL 구성 방식

Fly.io가 앱 이름 기준으로 `https://<app-name>.fly.dev` 도메인과 TLS 인증서를 자동 발급합니다. `fly.toml`의 `force_https = true`로 HTTP 요청은 HTTPS로 리다이렉트되고, 엣지가 내부 포트 8080으로 전달합니다.

최초 한 번 앱과 볼륨을 만듭니다.

```bash
fly apps create <고유한-app-name>
fly volumes create votes_data --app <고유한-app-name> --region nrt --size 1
fly deploy --app <고유한-app-name>
```

이후에는 GitHub 저장소에 아래를 설정해 두면 `main` push 때 테스트 통과 후 자동 배포됩니다.

- Actions variable `FLY_APP_NAME` — Fly 앱 이름
- Actions secret `FLY_API_TOKEN` — 해당 앱 범위 deploy token

두 값이 비어 있으면 워크플로는 테스트만 수행하고 배포 단계를 안전하게 건너뜁니다.

제출용 URL은 `https://jjajang-vs-jjamppong.fly.dev`입니다. 2026-09-15에 실제 Public URL 호출과 Fly Machine 재시작 후 데이터 유지까지 검증했습니다.

### 최종 검증 체크리스트

- [x] `POST /api/vote` 정상 투표 `201`
- [x] 동일 `voterId` 중복 투표 `409`
- [x] 비정상 요청 `422`
- [x] `GET /api/result` 실제 저장 데이터와 일치
- [x] `GET /health` `200`
- [x] 동시 고유 투표 100건 유실 없음
- [x] Dockerfile 원격 빌드 및 Fly Machine 실행
- [x] Public HTTPS URL 외부 호출
- [x] 실제 Machine 재시작 후 데이터와 중복 방지 규칙 유지

---

## 7. 구현하면서 중요하게 판단한 설계 사항

**중복 차단을 DB 제약으로 내렸습니다.** 애플리케이션에서 중복을 검사하면 코드는 읽기 쉬워지지만 동시 요청에서 깨집니다. 유일성이라는 규칙을 지킬 책임을 `PRIMARY KEY` 한 곳에 몰아두면, 경쟁 조건을 "처리"하는 대신 존재하지 않게 만들 수 있습니다.

**집계를 저장하지 않고 매번 계산합니다.** 카운터를 따로 두면 증가 연산이 또 하나의 동시성 문제가 되고 원본과 어긋날 수 있습니다. 이 규모에서는 `COUNT`가 충분히 빠르므로 정확성을 택했습니다.

**DB 경로를 주입받는 app factory로 만들었습니다.** `create_app(path)` 구조 덕분에 테스트가 임시 파일로 완전히 격리되고, 같은 경로로 앱을 두 번 만들어 프로세스 재시작까지 테스트로 재현할 수 있었습니다. 영속성을 "설정했으니 되겠지"가 아니라 실제로 검증하기 위한 선택입니다.

**헬스체크가 DB를 실제로 건드립니다.** `GET /health`는 `SELECT 1`을 던진 뒤 응답합니다. 프로세스만 살아 있고 볼륨이 안 붙은 상태를 정상으로 보고하지 않기 위해서입니다.

**확장성 대신 정합성을 택했습니다.** SQLite 파일이 한 볼륨에 묶여 있어 Machine을 늘릴 수 없고, `workers=1`도 같은 이유입니다. 이 과제 규모에서는 분산 DB를 들이는 것보다 구성요소를 줄이는 쪽이 정합성을 보장하기 쉽다고 판단했습니다. 트래픽이 커지면 PostgreSQL로 옮기되 `UNIQUE` 제약과 트랜잭션으로 **같은 규칙을 그대로** 유지하는 것이 다음 수순입니다.

**비용 대신 콜드 스타트를 감수했습니다.** `min_machines_running = 0` + `auto_stop_machines`로 유휴 시 Machine이 정지합니다. 첫 요청에 기동 지연이 붙지만, 상시 트래픽이 없는 과제 환경에서는 합리적인 교환이라고 봤습니다.

**컨테이너는 non-root로 실행합니다.** 이미지에서 `app` 사용자를 만들어 `/app`과 `/data` 소유권을 넘기고 `USER app`으로 전환합니다. `.dockerignore`로 `tests`, `.venv`, `*.db`를 제외해 빌드 컨텍스트도 줄였습니다.
