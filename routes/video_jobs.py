from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from config import settings
from models import SubmitVideoJobRequest, UpdateVideoJobRequest, VideoJob, VideoJobListResponse
from services.video_job_store import (
    get_video_job,
    list_pending_video_jobs,
    submit_video_job,
    update_video_job,
)


router = APIRouter(tags=["video-jobs"])


def _enforce_worker_token(x_worker_token: str | None) -> None:
    configured_token = settings.video_worker_token
    if not configured_token:
        return
    if x_worker_token != configured_token:
        raise HTTPException(status_code=401, detail="Invalid worker token.")


@router.post("/video-jobs", response_model=VideoJob)
def submit_video_job_route(payload: SubmitVideoJobRequest) -> VideoJob:
    return submit_video_job(payload)


@router.get("/video-jobs/pending", response_model=VideoJobListResponse)
def list_pending_video_jobs_route(
    limit: int = Query(default=5, ge=1, le=20),
    x_worker_token: str | None = Header(default=None),
) -> VideoJobListResponse:
    _enforce_worker_token(x_worker_token)
    return list_pending_video_jobs(limit=limit)


@router.get("/video-jobs/{job_id}", response_model=VideoJob)
def get_video_job_route(job_id: str) -> VideoJob:
    return get_video_job(job_id)


@router.post("/video-jobs/{job_id}/update", response_model=VideoJob)
def update_video_job_route(
    job_id: str,
    payload: UpdateVideoJobRequest,
    x_worker_token: str | None = Header(default=None),
) -> VideoJob:
    _enforce_worker_token(x_worker_token)
    return update_video_job(job_id, payload)
