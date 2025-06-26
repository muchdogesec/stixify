
import io
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch, call
import pytest
from stixify.worker.tasks import job_completed_with_error, new_task, process_post
from stixify.web import models
from dogesec_commons.stixifier.stixifier import StixifyProcessor

from stixify.worker import pdf_converter

@pytest.mark.parametrize(
    'file',
    [
        'tests/example_files/file_example_XLS_10.xls',
        'tests/example_files/file-sample_100kB.doc',
        'tests/example_files/sample.txt',
        'tests/example_files/sample.md',
        'tests/example_files/sample.png',
    ]
)
def test_make_conversion(file):
    output_path = "/tmp/outfile.pdf"
    result = pdf_converter.make_conversion(file, output_path)
    with open(output_path, 'rb') as ff:
        assert tuple(ff.read(4)) == (0x25,0x50,0x44,0x46)
    os.remove(output_path)
