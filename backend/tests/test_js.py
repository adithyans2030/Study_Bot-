"""Runs the JavaScript unit tests (Node's built-in runner) as part of the Python suite."""
import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = Path(__file__).parent / "js" / "rich.test.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_rich_text_parser_js_tests_pass():
    result = subprocess.run(["node", "--test", str(JS_TESTS)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
