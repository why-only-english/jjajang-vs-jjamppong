from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


def test_vote_result_validation_and_duplicate(tmp_path):
    app = create_app(str(tmp_path / "votes.db"))
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert root.json()["status"] == "running"
        assert client.get("/health").status_code == 200
        assert client.get("/api/result").json() == {
            "jajang": 0,
            "jjamppong": 0,
            "total": 0,
        }

        response = client.post(
            "/api/vote", json={"choice": "jajang", "voterId": "user-123"}
        )
        assert response.status_code == 201
        assert client.post(
            "/api/vote", json={"choice": "jjamppong", "voterId": "user-123"}
        ).status_code == 409
        assert client.post(
            "/api/vote", json={"choice": "invalid", "voterId": "user-999"}
        ).status_code == 422
        assert client.post(
            "/api/vote", json={"choice": "jajang"}
        ).status_code == 422
        assert client.get("/api/result").json() == {
            "jajang": 1,
            "jjamppong": 0,
            "total": 1,
        }


def test_concurrent_votes_are_not_lost_and_duplicate_is_atomic(tmp_path):
    app = create_app(str(tmp_path / "votes.db"))
    with TestClient(app) as client:
        unique_votes = [
            (f"user-{index}", "jajang" if index % 2 == 0 else "jjamppong")
            for index in range(100)
        ]

        def submit(vote):
            voter_id, choice = vote
            return client.post(
                "/api/vote", json={"choice": choice, "voterId": voter_id}
            ).status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            statuses = list(pool.map(submit, unique_votes))
        assert statuses.count(201) == 100

        with ThreadPoolExecutor(max_workers=20) as pool:
            duplicate_statuses = list(
                pool.map(submit, [("same-user", "jajang")] * 20)
            )
        assert duplicate_statuses.count(201) == 1
        assert duplicate_statuses.count(409) == 19
        assert client.get("/api/result").json() == {
            "jajang": 51,
            "jjamppong": 50,
            "total": 101,
        }


def test_data_and_duplicate_rule_survive_application_restart(tmp_path):
    database_path = str(tmp_path / "votes.db")

    with TestClient(create_app(database_path)) as client:
        assert client.post(
            "/api/vote", json={"choice": "jjamppong", "voterId": "persistent-user"}
        ).status_code == 201

    # 새 FastAPI 애플리케이션을 같은 DB 파일로 생성해 프로세스 재시작을 모사한다.
    with TestClient(create_app(database_path)) as restarted_client:
        assert restarted_client.get("/api/result").json() == {
            "jajang": 0,
            "jjamppong": 1,
            "total": 1,
        }
        assert restarted_client.post(
            "/api/vote", json={"choice": "jajang", "voterId": "persistent-user"}
        ).status_code == 409
