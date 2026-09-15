# 작업 진행 내역

마지막 갱신: 2026-09-15 KST Fly 배포 및 재시작 영속성 검증 완료

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
- [x] README 최종 제출본 갱신

## 진행/대기

- [x] 로컬 Python 테스트 실행 (3 tests passed, 동시 요청/재시작 모사 포함)
- [x] 애플리케이션 재생성 후 데이터/중복 규칙 유지 테스트 추가
- [x] Fly 원격 Docker 빌드 성공 (image size 51MB)
- [x] 실제 Fly Machine 재시작 영속성 검증
- [x] Git 저장소 생성 및 GitHub remote 연결
- [x] GitHub `main` push
- [x] Fly 앱/1GB 암호화 Volume 생성 및 최초 배포
- [x] Public URL 외부 호출 검증
- [x] 루트 URL 안내 응답 추가 (`GET /`)
- [x] Session 2 상호 API 테스트용 smoke script 작성
- [x] Session 2 전체 Public API 테스트 스크립트 작성 및 실행
- [x] Session 2 제출용 테스트 결과 보고서 작성

## 검증 기록

- `.venv\\Scripts\\python -m pytest -q`: 성공
- 동시 고유 voterId 100건: 100건 성공, 집계 유실 없음
- 동일 voterId 동시 20건: 1건 성공/19건 409
- 이 PC에서 확인되지 않은 명령: `docker`, `gh`
- GitHub 저장소: https://github.com/why-only-english/jjajang-vs-jjamppong
- 로컬 초기 커밋: `49d46b8 feat: implement persistent voting API`
- Fly 설정 전에는 GitHub Actions가 테스트만 수행하고 배포는 안전하게 건너뜀
- 이 저장소의 Git 작성자·push 사용자 설정을 `why-only-english`로 변경 (전역 jgmoon 설정은 유지)
- Fly CLI `v0.4.103` 설치 및 로그인 완료
- Fly app: `jjajang-vs-jjamppong`, volume: `votes_data` (nrt, 1GB, encrypted)
- Public URL: https://jjajang-vs-jjamppong.fly.dev
- Public smoke test: health/result/vote/duplicate/count 검증 모두 성공
- 실제 Machine 재시작: 결과 `2표` 유지, 기존 voterId 재투표 `409` 확인
- Session 2 실행 `s2-aa4ccf1db14e`: 고유 ID 100건 전부 성공, 동일 ID 20건 중 1건만 성공
- Session 2 집계: 시작 58 → 종료 161, 성공 요청 103건과 증가량 정확히 일치
- Session 2 재시작: Health 정상, 기존 voterId `409`; 외부 동시 요청으로 total은 163 → 165 증가
- 최종 Session 2 실행 `s2-d500ebe49560`: 시작 210 → 종료 313, 성공 103건과 정확히 일치
- 최종 재시작 검증: `176/138/314`가 재시작 후 동일하게 유지되고 기존 voterId `409`
- Session 2 산출물 경로: `C:\Users\문종근\Desktop\문종근\20260915\session2-산출물-문종근`
- Session 2 제출 형식 ①~⑤ 최종 대조 및 사실/추정/개선 구분 완료
- Session 2 산출물 ZIP 생성 및 저장소 추가: `session2-산출물-문종근.zip`
- ZIP SHA-256: `91C82D7C750921D47689CF5F074D251289B1510AAA72B3B69B8E9D75CBD218FD`

## 사용자에게 필요한 정보

- GitHub 저장소 URL(새 저장소라면 원하는 저장소 이름과 공개/비공개 여부)
- GitHub 인증: 이 PC에서 로그인 또는 push 가능한 자격 증명
- [x] Fly.io 계정 생성 완료 (Personal 조직)
- [x] Fly 앱 생성: `jjajang-vs-jjamppong` (Personal 조직)
- 앱 범위 `FLY_API_TOKEN` (채팅에 붙이지 말고 GitHub Actions secret으로 직접 등록 권장)
