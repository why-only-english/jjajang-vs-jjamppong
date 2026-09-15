"""다른 지원자의 Public URL도 빠르게 검증하는 표준 라이브러리 스크립트."""

import json
import sys
import time
import urllib.error
import urllib.request


def request(base_url: str, path: str, method: str = "GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        payload = json.loads(error.read())
        return error.code, payload


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/smoke_test.py https://app.example.com")
        return 2

    base_url = sys.argv[1]
    voter_id = f"smoke-{int(time.time() * 1000)}"
    before_status, before = request(base_url, "/api/result")
    health_status, health = request(base_url, "/health")
    vote_status, vote = request(
        base_url,
        "/api/vote",
        "POST",
        {"choice": "jajang", "voterId": voter_id},
    )
    duplicate_status, duplicate = request(
        base_url,
        "/api/vote",
        "POST",
        {"choice": "jjamppong", "voterId": voter_id},
    )
    after_status, after = request(base_url, "/api/result")

    checks = {
        "health_200": health_status == 200,
        "result_200": before_status == after_status == 200,
        "vote_201": vote_status == 201,
        "duplicate_409": duplicate_status == 409,
        "total_incremented": after.get("total") == before.get("total", -1) + 1,
        "jajang_incremented": after.get("jajang") == before.get("jajang", -1) + 1,
    }
    print(json.dumps({"checks": checks, "health": health, "vote": vote,
                      "duplicate": duplicate, "before": before, "after": after},
                     ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
