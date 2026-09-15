"""Session 2 공개 API 기능·동시성·정합성 테스트 (표준 라이브러리만 사용)."""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor


def request(base_url: str, path: str, method: str = "GET", body=None, raw=None):
    if raw is not None:
        data = raw
    elif body is not None:
        data = json.dumps(body).encode()
    else:
        data = None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = response.read()
            return response.status, json.loads(payload), time.perf_counter() - started
    except urllib.error.HTTPError as error:
        payload = error.read()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload.decode(errors="replace")}
        return error.code, parsed, time.perf_counter() - started


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/session2_test.py https://public-url")
        return 2

    base_url = sys.argv[1].rstrip("/")
    run_id = f"s2-{uuid.uuid4().hex[:12]}"
    failures: list[str] = []
    evidence: dict[str, object] = {"target": base_url, "runId": run_id}

    def check(name: str, condition: bool, detail: object) -> None:
        evidence[name] = {"passed": condition, "detail": detail}
        if not condition:
            failures.append(name)

    health_status, health, _ = request(base_url, "/health")
    before_status, before, _ = request(base_url, "/api/result")
    check("health", health_status == 200 and health.get("status") == "ok", health)
    check("initial_result", before_status == 200, before)
    check(
        "initial_invariant",
        before.get("jajang", -1) + before.get("jjamppong", -1)
        == before.get("total", -2),
        before,
    )

    validation_cases = {
        "invalid_choice": ({"choice": "ramen", "voterId": f"{run_id}-bad"}, None),
        "missing_choice": ({"voterId": f"{run_id}-missing-choice"}, None),
        "missing_voter_id": ({"choice": "jajang"}, None),
        "empty_voter_id": ({"choice": "jajang", "voterId": ""}, None),
        "malformed_json": (None, b'{"choice":"jajang","voterId":'),
    }
    validation_results = {}
    for name, (body, raw) in validation_cases.items():
        status, payload, _ = request(
            base_url, "/api/vote", "POST", body=body, raw=raw
        )
        validation_results[name] = {"status": status, "body": payload}
    check(
        "validation",
        all(item["status"] == 422 for item in validation_results.values()),
        validation_results,
    )

    normal_ids = [f"{run_id}-normal-jajang", f"{run_id}-normal-jjamppong"]
    normal_statuses = [
        request(
            base_url,
            "/api/vote",
            "POST",
            {"choice": choice, "voterId": voter_id},
        )[0]
        for voter_id, choice in zip(normal_ids, ("jajang", "jjamppong"))
    ]
    duplicate_status = request(
        base_url,
        "/api/vote",
        "POST",
        {"choice": "jjamppong", "voterId": normal_ids[0]},
    )[0]
    check("normal_votes", normal_statuses == [201, 201], normal_statuses)
    check("sequential_duplicate", duplicate_status == 409, duplicate_status)

    same_vote = {"choice": "jajang", "voterId": f"{run_id}-same-concurrent"}

    def submit_same(_):
        return request(base_url, "/api/vote", "POST", same_vote)[0]

    with ThreadPoolExecutor(max_workers=20) as pool:
        same_statuses = list(pool.map(submit_same, range(20)))
    check(
        "same_voter_concurrent",
        same_statuses.count(201) == 1 and same_statuses.count(409) == 19,
        {"201": same_statuses.count(201), "409": same_statuses.count(409)},
    )

    unique_votes = [
        {
            "choice": "jajang" if index % 2 == 0 else "jjamppong",
            "voterId": f"{run_id}-unique-{index}",
        }
        for index in range(100)
    ]

    def submit_unique(vote):
        return request(base_url, "/api/vote", "POST", vote)[0]

    with ThreadPoolExecutor(max_workers=20) as pool:
        unique_statuses = list(pool.map(submit_unique, unique_votes))
    check(
        "unique_voters_concurrent",
        unique_statuses.count(201) == 100,
        {"201": unique_statuses.count(201), "other": 100 - unique_statuses.count(201)},
    )

    after_status, after, _ = request(base_url, "/api/result")
    expected_jajang_delta = 52  # 정상 1 + 동일 ID 경쟁 성공 1 + 고유 ID 50
    expected_jjamppong_delta = 51  # 정상 1 + 고유 ID 50
    expected_total_delta = 103
    delta = {
        "jajang": after.get("jajang", -1) - before.get("jajang", 0),
        "jjamppong": after.get("jjamppong", -1) - before.get("jjamppong", 0),
        "total": after.get("total", -1) - before.get("total", 0),
    }
    check("final_result", after_status == 200, after)
    check(
        "final_invariant",
        after.get("jajang", -1) + after.get("jjamppong", -1)
        == after.get("total", -2),
        after,
    )
    check(
        "exact_delta",
        delta
        == {
            "jajang": expected_jajang_delta,
            "jjamppong": expected_jjamppong_delta,
            "total": expected_total_delta,
        },
        {
            "before": before,
            "after": after,
            "actualDelta": delta,
            "expectedDelta": {
                "jajang": expected_jajang_delta,
                "jjamppong": expected_jjamppong_delta,
                "total": expected_total_delta,
            },
        },
    )

    evidence["restartProbeVoterId"] = normal_ids[0]
    evidence["summary"] = {
        "passed": not failures,
        "failedChecks": failures,
        "successfulVotesExpected": expected_total_delta,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
