import sys
from types import ModuleType
from unittest.mock import Mock

from stixify.worker.tasks import process_post


def test_process_post_delegates_to_process_post_impl(monkeypatch):
    process_post_impl = Mock(return_value="job-id")
    process_post_module = ModuleType("stixify.worker.process_post")
    process_post_module.process_post_impl = process_post_impl
    monkeypatch.setitem(
        sys.modules, "stixify.worker.process_post", process_post_module
    )

    assert process_post.run("job-id", "file-id", "extra") == "job-id"
    process_post_impl.assert_called_once_with("job-id", "file-id", "extra")
    assert process_post.name == "stixify.worker.tasks.process_post"
