"""
FastAPI backend for ReconDragon worker architecture.

Provides REST API endpoints for job management and status tracking.
"""

import os
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from redis import Redis
from rq import Queue
import json

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "recon_queue"
DB_URL = os.getenv("DB_URL", "./recon.db")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis and RQ setup
redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(QUEUE_NAME, connection=redis_conn)

app = FastAPI(title="ReconDragon API", description="Worker architecture API for ReconDragon")

class JobRequest(BaseModel):
    module: str  # e.g., "http_probe"
    target: str
    outdir: str

@app.post("/jobs")
async def create_job(job_req: JobRequest) -> Dict[str, Any]:
    """
    Create and enqueue a new job.

    Enqueues the job in Redis queue for processing by worker.
    """
    try:
        # Enqueue the job with retry logic
        job = queue.enqueue(
            "worker.runner.run_module",
            args=[job_req.module, job_req.target, job_req.outdir],
            job_timeout=3600,  # 1 hour timeout
            result_ttl=86400,  # Keep results for 24 hours
            failure_ttl=86400,
            retry=3,  # Retry failed jobs up to 3 times
            retry_delay=60  # Wait 60 seconds between retries
        )

        logger.info(f"Job {job.id} enqueued for module {job_req.module} on target {job_req.target}")

        return {
            "job_id": job.id,
            "status": "queued",
            "module": job_req.module,
            "target": job_req.target,
            "outdir": job_req.outdir
        }

    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {str(e)}")

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status and details of a job.
    """
    try:
        job = queue.fetch_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = {
            "job_id": job.id,
            "status": job.get_status(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "module": job.args[0] if job.args else None,
            "target": job.args[1] if len(job.args) > 1 else None,
            "outdir": job.args[2] if len(job.args) > 2 else None,
        }

        # Include result if job is finished
        if job.is_finished:
            response["result"] = job.result
        elif job.is_failed:
            response["error"] = str(job.exc_info) if job.exc_info else "Unknown error"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@app.get("/workspaces")
async def list_workspaces() -> List[Dict[str, Any]]:
    """List all workspaces."""
    try:
        conn = sqlite3.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM workspaces")
        workspaces = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        conn.close()
        return workspaces
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list workspaces: {str(e)}")

@app.get("/jobs")
async def list_jobs(workspace: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """List all jobs, optionally filtered by workspace."""
    try:
        conn = sqlite3.connect(DB_URL)
        cursor = conn.cursor()
        if workspace:
            cursor.execute("SELECT * FROM jobs WHERE workspace=?", (workspace,))
        else:
            cursor.execute("SELECT * FROM jobs")
        jobs = []
        for row in cursor.fetchall():
            job_data = {
                "id": row[0],
                "workspace": row[1],
                "target": row[2],
                "modules": json.loads(row[3]),
                "status": row[4],
                "created_at": row[5]
            }
            jobs.append(job_data)
        conn.close()
        return jobs
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)