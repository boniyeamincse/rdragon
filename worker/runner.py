"""
Worker runner for ReconDragon.

Processes jobs from Redis queue, executes reconnaissance modules,
and handles results with proper logging and error handling.
"""

import os
import sys
import logging
import signal
import time
import importlib
from pathlib import Path
from typing import Dict, Any, Optional
from redis import Redis
from rq import Worker, Queue, Connection, get_current_job

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "recon_queue"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, requesting graceful shutdown...")
    shutdown_requested = True

def run_module(module_name: str, target: str, outdir: str) -> Dict[str, Any]:
    """
    Execute a reconnaissance module.

    Dynamically imports and runs the specified module with given parameters.

    Args:
        module_name: Name of the module to run (e.g., 'http_probe')
        target: Target for the module
        outdir: Output directory

    Returns:
        Dict containing module execution results
    """
    job = get_current_job()
    logger.info(f"Starting job {job.id}: {module_name} on {target}")

    try:
        # Import the module dynamically
        module_path = f"modules.{module_name}"
        module = importlib.import_module(module_path)

        # Get the module class (assuming it's named like HttpProbeModule)
        # Try to find the class that ends with 'Module'
        module_classes = [cls for cls in dir(module) if cls.endswith('Module') and not cls.startswith('_')]
        if not module_classes:
            raise ImportError(f"No module class found in {module_path}")

        module_class_name = module_classes[0]  # Take the first one
        module_class = getattr(module, module_class_name)

        # Instantiate and run
        instance = module_class()
        result = instance.run(target, outdir)

        logger.info(f"Job {job.id} completed successfully: {module_name}")
        return result

    except Exception as e:
        logger.error(f"Job {job.id} failed: {str(e)}")
        raise

def main():
    """Main worker function with graceful shutdown."""
    global shutdown_requested

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting ReconDragon worker...")

    # Setup Redis connection
    redis_conn = Redis.from_url(REDIS_URL)

    # Create worker
    with Connection(redis_conn):
        worker = Worker(
            [QUEUE_NAME],
            connection=redis_conn,
            name=f"recon-worker-{os.getpid()}",
            default_worker_ttl=30,  # Worker dies after 30s of inactivity
            default_result_ttl=86400,  # Keep results for 24 hours
            default_failure_ttl=86400
        )

        logger.info(f"Worker {worker.name} listening on queue '{QUEUE_NAME}'")

        # Work loop with shutdown check
        while not shutdown_requested:
            try:
                # Process one job at a time with timeout
                worker.work(burst=True, max_jobs=1)
                time.sleep(1)  # Small delay between jobs
            except Exception as e:
                logger.error(f"Worker error: {e}")
                if shutdown_requested:
                    break
                time.sleep(5)  # Wait before retrying

        logger.info("Worker shutting down gracefully...")

if __name__ == "__main__":
    main()