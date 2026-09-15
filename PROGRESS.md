# 작업 진행 내역

마지막 갱신: 2026-09-15 KST 기본 구현 및 로컬 테스트 완료

## 결정

- 아키텍처: FastAPI + SQLite + Docker + Fly.io 단일 Machine/Volume
- 선택 이유: 40분 내 구현·테스트·Public URL·재시작 영속성을 가장 적은 구성요소로 충족
- 동시성: `voter_id` PRIMARY KEY와 SQLite 트랜잭션으로 중복 투표 원자적 차단
- 영속성: DB 파일을 `/data`에 두고 Docker/Fly 영구 볼륨 사용

## 완료

- [x] API 기본 구현 (`POST /api/vote`, `GET /api/result`, `GET /health`)
- [x] 입력 검증과 409 중복 응답
- [x] SQLite WAL/timeout 및 영구 데이터 경로
- [x] Dockerfile, Docker Compose
- [x] 단위/API/동시성 테스트 작성
- [x] Fly.io 설정과 GitHub Actions 작성
- [x] README 초안

## 진행/대기

- [x] 로컬 Python 테스트 실행 (2 tests passed, 동시 요청 포함)
- [x] 애플리케이션 재생성 후 데이터/중복 규칙 유지 테스트 추가
- [ ] Docker 빌드/재시작 영속성 검증 (현재 PC Docker 확인 필요)
- [ ] Git 저장소 생성 및 GitHub push
- [ ] Fly 앱/Volume 생성 및 최초 배포
- [ ] Public URL 외부 호출 검증
- [x] Session 2 상호 API 테스트용 smoke script 작성

## 검증 기록

- `.venv\\Scripts\\python -m pytest -q`: 성공
- 동시 고유 voterId 100건: 100건 성공, 집계 유실 없음
- 동일 voterId 동시 20건: 1건 성공/19건 409
- 이 PC에서 확인되지 않은 명령: `docker`, `gh`, `flyctl`
- Git 저장소 `main` 브랜치 초기화 완료 (아직 remote/commit 없음)

## 사용자에게 필요한 정보

- GitHub 저장소 URL(새 저장소라면 원하는 저장소 이름과 공개/비공개 여부)
- GitHub 인증: 이 PC에서 로그인 또는 push 가능한 자격 증명
- Fly.io 계정/조직과 고유 앱 이름
- 앱 범위 `FLY_API_TOKEN` (채팅에 붙이지 말고 GitHub Actions secret으로 직접 등록 권장)
