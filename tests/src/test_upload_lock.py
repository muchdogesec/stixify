import os
import time
import uuid
from threading import Barrier, Event, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from redis import Redis
from redis.exceptions import ConnectionError, LockNotOwnedError

from stixify.worker import upload_lock as module


@pytest.fixture
def mocked_redis(monkeypatch):
    client = MagicMock()
    client.lock.return_value.acquire.return_value = True
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(module.Redis, "from_url", factory)
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(CELERY_BROKER_URL="redis://test/0")
    )
    return client, client.lock.return_value, factory


def test_upload_lock_releases_owned_slot(mocked_redis):
    client, lock, factory = mocked_redis
    with module.upload_lock("job", wait_timeout=2):
        lock.release.assert_not_called()

    client.lock.assert_called_once_with(
        module.UPLOAD_LOCK_KEY,
        timeout=module.LOCK_TIMEOUT,
        blocking_timeout=2,
        thread_local=False,
    )
    assert factory.call_args.kwargs["socket_timeout"] == module.SOCKET_TIMEOUT
    lock.release.assert_called_once_with()
    client.close.assert_called_once_with()


@pytest.mark.parametrize("acquire_error", [None, ConnectionError("redis down")])
def test_unacquired_lock_is_never_released(mocked_redis, acquire_error):
    client, lock, _ = mocked_redis
    lock.acquire.return_value = False
    lock.acquire.side_effect = acquire_error
    with pytest.raises(type(acquire_error) if acquire_error else TimeoutError):
        with module.upload_lock("job", wait_timeout=0):
            pytest.fail("Upload must not run without its lock")

    lock.release.assert_not_called()
    client.close.assert_called_once_with()


@pytest.mark.parametrize("error", [ValueError("upload failed"), SystemExit("exited")])
def test_cleanup_does_not_replace_original_error(mocked_redis, error):
    client, lock, _ = mocked_redis
    lock.release.side_effect = ConnectionError("redis down")
    client.close.side_effect = ConnectionError("close failed")
    with pytest.raises(type(error)) as raised:
        with module.upload_lock("job"):
            raise error

    assert raised.value is error
    lock.release.assert_called_once_with()


def test_release_failure_is_reported_after_successful_upload(mocked_redis):
    _, lock, _ = mocked_redis
    error = LockNotOwnedError("lease lost")
    lock.release.side_effect = error
    with pytest.raises(RuntimeError, match="Upload lock failed") as raised:
        with module.upload_lock("job"):
            pass
    assert raised.value.__cause__ is error


def test_thread_start_failure_releases_lock(mocked_redis, monkeypatch):
    _, lock, _ = mocked_redis
    thread = MagicMock(ident=None)
    thread.start.side_effect = RuntimeError("cannot start thread")
    monkeypatch.setattr(module, "Thread", MagicMock(return_value=thread))
    with pytest.raises(RuntimeError, match="cannot start thread"):
        with module.upload_lock("job"):
            pytest.fail("Upload must not run without renewal")
    lock.release.assert_called_once_with()


@pytest.mark.parametrize("upload_error", [None, ValueError("upload failed")])
def test_renewal_failure_is_reported_without_replacing_upload_error(
    mocked_redis, monkeypatch, upload_error
):
    _, lock, _ = mocked_redis
    renewal_attempted = Event()
    renewal_error = LockNotOwnedError("lease expired")

    def fail_renewal():
        renewal_attempted.set()
        raise renewal_error

    lock.reacquire.side_effect = fail_renewal
    monkeypatch.setattr(module, "LOCK_TIMEOUT", 0.03)
    with pytest.raises(ValueError if upload_error else RuntimeError) as raised:
        with module.upload_lock("job"):
            assert renewal_attempted.wait(2)
            if upload_error:
                raise upload_error

    if upload_error:
        assert raised.value is upload_error
    else:
        assert raised.value.__cause__ is renewal_error
    lock.release.assert_called_once_with()


@pytest.fixture
def real_redis(monkeypatch):
    """Opt-in integration tests use only a unique, expiring key; never flush."""
    url = os.environ.get("STIXIFY_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set STIXIFY_TEST_REDIS_URL to run Redis ownership tests")
    client = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
    client.ping()
    key = f"stixify:test:upload-lock:{uuid.uuid4()}"
    monkeypatch.setattr(module, "UPLOAD_LOCK_KEY", key)
    monkeypatch.setattr(module, "settings", SimpleNamespace(CELERY_BROKER_URL=url))
    try:
        yield client, key
    finally:
        client.delete(key)
        client.close()


def test_real_redis_contenders_cannot_overlap(real_redis):
    client, key = real_redis
    with module.upload_lock("first"):
        owner = client.get(key)
        with pytest.raises(TimeoutError):
            with module.upload_lock("second", wait_timeout=0.05):
                pytest.fail("Another upload already owns the slot")
        assert client.get(key) == owner
    assert client.get(key) is None
    with module.upload_lock("second", wait_timeout=0):
        assert client.get(key) is not None


def test_real_redis_simultaneous_contenders_take_only_one_slot(real_redis):
    client, key = real_redis
    start = Barrier(3)
    rejected = Event()
    release = Event()
    owners = []
    errors = []

    def contend(job_id):
        try:
            start.wait(2)
            with module.upload_lock(job_id, wait_timeout=0.1):
                owners.append(job_id)
                assert release.wait(2)
        except TimeoutError:
            rejected.set()
        except BaseException as exc:
            errors.append(exc)
            rejected.set()

    threads = [Thread(target=contend, args=(job_id,)) for job_id in ("a", "b")]
    for thread in threads:
        thread.start()
    try:
        start.wait(2)
        assert rejected.wait(2)
        assert len(owners) == 1
        assert client.get(key) is not None
    finally:
        release.set()
        for thread in threads:
            thread.join(2)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert client.get(key) is None


def test_real_redis_renews_beyond_original_expiry(real_redis, monkeypatch):
    client, key = real_redis
    monkeypatch.setattr(module, "LOCK_TIMEOUT", 0.3)
    with module.upload_lock("long-upload"):
        owner = client.get(key)
        time.sleep(0.7)
        assert client.get(key) == owner
        assert client.pttl(key) > 0
        with pytest.raises(TimeoutError):
            with module.upload_lock("contender", wait_timeout=0):
                pytest.fail("The active upload lease should have been renewed")
    assert client.get(key) is None


def test_real_redis_stale_owner_cannot_release_successor(real_redis):
    client, key = real_redis
    replacement = client.lock(key, timeout=5)
    error = ValueError("upload failed after lease loss")
    with pytest.raises(ValueError) as raised:
        with module.upload_lock("old-owner"):
            client.pexpire(key, 1)
            time.sleep(0.02)
            assert replacement.acquire(blocking=False)
            raise error
    assert raised.value is error
    assert replacement.owned()
    replacement.release()


def test_real_redis_abandoned_owner_expires(real_redis):
    client, key = real_redis
    abandoned = client.lock(key, timeout=0.05)
    assert abandoned.acquire(blocking=False)
    time.sleep(0.1)
    with module.upload_lock("replacement", wait_timeout=0):
        assert client.get(key) != abandoned.local.token
    assert client.get(key) is None
