# 짜장면 vs 짬뽕 투표 API

40분 구현 과제를 위한 최소 운영형 백엔드입니다.

## 기술과 설계

- Python 3.12, FastAPI, Uvicorn
- SQLite 파일 DB (`/data/votes.db`)
- `voter_id` 기본키/UNIQUE 제약으로 중복 투표를 DB에서 원자적으로 차단
- SQLite WAL, busy timeout, 짧은 INSERT 트랜잭션으로 동시 쓰기 처리
- Docker named volume 또는 Fly Volume을 `/data`에 연결해 재시작 후 데이터 유지
- 단일 Fly Machine/단일 Uvicorn worker 구성. 이 과제 규모에서는 분산 DB 없이 정합성을 가장 단순하게 보장

## 로컬 실행

```bash
docker compose up --build -d
curl http://localhost:8080/health
```

Docker Compose를 사용하지 않을 경우:

```bash
docker build -t backend-test .
docker run --name backend-test -p 8080:8080 -v votes-data:/data --restart unless-stopped backend-test
```

## API

```bash
curl -X POST http://localhost:8080/api/vote \
  -H "Content-Type: application/json" \
  -d '{"choice":"jajang","voterId":"user-123"}'

curl http://localhost:8080/api/result
curl http://localhost:8080/health
```

- 정상 투표: `201 Created`
- 같은 `voterId`의 중복 투표: `409 Conflict`
- 누락/잘못된 `choice` 또는 `voterId`: `422 Unprocessable Entity`

## 테스트

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Windows PowerShell에서는 `.venv\\Scripts\\python -m pytest -q`를 사용합니다.

테스트에는 100건 동시 투표 유실 여부와 동일 voterId 20건 동시 요청 시 1건만 성공하는 검증이 포함됩니다.

다른 사람의 Public URL을 Session 2에서 빠르게 점검하려면:

```bash
python scripts/smoke_test.py https://상대방-public-url
```

## Fly.io 배포

최초 한 번 앱과 1GB 영구 볼륨을 만듭니다.

```bash
fly apps create <고유한-app-name>
fly volumes create votes_data --app <고유한-app-name> --region nrt --size 1
fly deploy --app <고유한-app-name>
```

GitHub 저장소에 다음을 설정하면 `main` push 때 테스트 후 자동 배포됩니다.

- Actions variable `FLY_APP_NAME`: Fly 앱 이름
- Actions secret `FLY_API_TOKEN`: 해당 앱 범위 deploy token

Public URL은 `https://<고유한-app-name>.fly.dev`이고 `/health`, `/api/result`를 붙여 제출합니다.

> SQLite 파일이 한 Fly Volume에 있으므로 수평 확장은 하지 않습니다. 더 큰 운영 규모라면 PostgreSQL의 UNIQUE 제약과 트랜잭션으로 같은 규칙을 유지합니다.
