from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from models import SubmitVideoJobRequest, UpdateVideoJobRequest, VideoJob, VideoJobListResponse


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "video_jobs.json"
STORE_LOCK = Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")


def _read_jobs() -> list[dict]:
    _ensure_store()
    raw = DATA_FILE.read_text(encoding="utf-8").strip() or "[]"
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return data


def _write_jobs(jobs: list[dict]) -> None:
    _ensure_store()
    DATA_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def submit_video_job(payload: SubmitVideoJobRequest) -> VideoJob:
    with STORE_LOCK:
        jobs = _read_jobs()
        now = _utcnow().isoformat()
        job = VideoJob(
            job_id=uuid4().hex,
            status="pending",
            story=payload.story,
            scene_count=payload.scene_count,
            clip_duration_seconds=payload.clip_duration_seconds,
            width=payload.width,
            height=payload.height,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        job_dict = job.model_dump(mode="json")
        job_dict["created_at"] = now
        job_dict["updated_at"] = now
        jobs.append(job_dict)
        _write_jobs(jobs)
        return VideoJob.model_validate(job_dict)


def get_video_job(job_id: str) -> VideoJob:
    with STORE_LOCK:
        jobs = _read_jobs()
        for job in jobs:
            if job.get("job_id") == job_id:
                return VideoJob.model_validate(job)
    raise HTTPException(status_code=404, detail="Video job not found.")


def list_pending_video_jobs(limit: int = 5) -> VideoJobListResponse:
    with STORE_LOCK:
        jobs = _read_jobs()
        pending = [
            VideoJob.model_validate(job)
            for job in jobs
            if job.get("status") == "pending"
        ]
    pending.sort(key=lambda item: item.created_at)
    return VideoJobListResponse(jobs=pending[:limit])


def update_video_job(job_id: str, payload: UpdateVideoJobRequest) -> VideoJob:
    with STORE_LOCK:
        jobs = _read_jobs()
        for index, job in enumerate(jobs):
            if job.get("job_id") != job_id:
                continue

            job["status"] = payload.status
            job["title"] = payload.title
            job["summary"] = payload.summary
            job["video_url"] = payload.video_url
            job["error"] = payload.error
            job["captions"] = payload.captions
            job["scenes"] = [scene.model_dump(mode="json") for scene in payload.scenes]
            job["updated_at"] = _utcnow().isoformat()
            jobs[index] = job
            _write_jobs(jobs)
            return VideoJob.model_validate(job)

    raise HTTPException(status_code=404, detail="Video job not found.")
