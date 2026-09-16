"""An ownership-checked Redis lease for the single Arango upload slot.

Stop workers using the legacy cache counter before deploying this lock.
"""

import logging
from contextlib import contextmanager
from threading import Event, Thread

from django.conf import settings
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


logger = logging.getLogger(__name__)
UPLOAD_LOCK_KEY = "stixify:arango_upload_lock"
LOCK_TIMEOUT = 300
SOCKET_TIMEOUT = 5


def _renew_lease(lock, stopped, errors, job_id):
    while not stopped.wait(LOCK_TIMEOUT / 3):
        try:
            lock.reacquire()
        except Exception as exc:
            errors.append(exc)
            logger.exception("Could not renew upload lock for job %s", job_id)
            return


@contextmanager
def upload_lock(job_id, wait_timeout=LOCK_TIMEOUT):
    """Serialize uploads, renew long-running uploads, and expire crashed owners.

    Each invocation gets a unique Redis lock token, including duplicate tasks
    for one job. Cleanup therefore cannot release a later owner's lease. If
    Redis becomes unavailable, cleanup errors never replace an upload error;
    otherwise they fail the task rather than silently reporting success.

    Like any lease without downstream fencing, this cannot prevent overlapping
    writes after a process suspension or Redis outage longer than the lease.
    """
    client = Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=SOCKET_TIMEOUT,
        socket_timeout=SOCKET_TIMEOUT,
        retry=Retry(NoBackoff(), 0),
    )
    lock = None
    acquired = False
    renewer = None
    stopped = Event()
    errors = []
    failed = True
    try:
        lock = client.lock(
            UPLOAD_LOCK_KEY,
            timeout=LOCK_TIMEOUT,
            blocking_timeout=wait_timeout,
            # Only this invocation shares the token with its renewal thread.
            thread_local=False,
        )
        if not lock.acquire():
            raise TimeoutError(
                f"Timeout waiting for arango upload slot after {wait_timeout}s"
            )
        acquired = True
        logger.info("Acquired upload lock for job %s", job_id)
        renewer = Thread(
            target=_renew_lease,
            args=(lock, stopped, errors, job_id),
            name=f"upload-lock-{job_id}",
            daemon=True,
        )
        renewer.start()
        yield
        failed = False
    finally:
        stopped.set()
        try:
            if renewer is not None and renewer.ident is not None:
                renewer.join()
        except Exception as exc:
            errors.append(exc)
            logger.exception("Could not stop upload lock renewal for job %s", job_id)
        finally:
            if acquired:
                try:
                    lock.release()
                    logger.info("Released upload lock for job %s", job_id)
                except Exception as exc:
                    errors.append(exc)
                    logger.exception("Could not release upload lock for job %s", job_id)
            try:
                client.close()
            except Exception:
                logger.exception("Could not close upload lock client for job %s", job_id)
        if errors and not failed:
            raise RuntimeError(f"Upload lock failed for job {job_id}: {errors[0]}") from errors[0]
