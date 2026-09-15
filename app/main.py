import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


class VoteRequest(BaseModel):
    choice: Literal["jajang", "jjamppong"]
    voterId: str = Field(min_length=1, max_length=128, pattern=r"^\S(?:.*\S)?$")


class VoteResult(BaseModel):
    jajang: int
    jjamppong: int
    total: int


class VoteStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS votes (
                    voter_id TEXT PRIMARY KEY,
                    choice TEXT NOT NULL CHECK (choice IN ('jajang', 'jjamppong')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def vote(self, voter_id: str, choice: str) -> None:
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO votes (voter_id, choice) VALUES (?, ?)",
                    (voter_id, choice),
                )
        except sqlite3.IntegrityError as error:
            if "votes.voter_id" in str(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="voterId has already voted",
                ) from error
            raise

    def result(self) -> VoteResult:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE choice = 'jajang'),
                    COUNT(*) FILTER (WHERE choice = 'jjamppong'),
                    COUNT(*)
                FROM votes
                """
            ).fetchone()
        assert row is not None
        return VoteResult(jajang=row[0], jjamppong=row[1], total=row[2])

    def check(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()


def create_app(database_path: str | None = None) -> FastAPI:
    path = database_path or os.getenv("DATABASE_PATH", "/data/votes.db")
    store = VoteStore(path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        yield

    api = FastAPI(title="Jajang vs Jjamppong Vote API", lifespan=lifespan)

    @api.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "Jajang vs Jjamppong Vote API",
            "status": "running",
            "endpoints": {
                "health": "GET /health",
                "result": "GET /api/result",
                "vote": "POST /api/vote",
                "docs": "GET /docs",
            },
        }

    @api.post("/api/vote", status_code=status.HTTP_201_CREATED)
    def vote(request: VoteRequest) -> dict[str, str]:
        store.vote(request.voterId, request.choice)
        return {"status": "accepted"}

    @api.get("/api/result", response_model=VoteResult)
    def result() -> VoteResult:
        return store.result()

    @api.get("/health")
    def health() -> dict[str, str]:
        store.check()
        return {"status": "ok"}

    return api


app = create_app()
