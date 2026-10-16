import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ProducerTests(unittest.TestCase):
    def test_native_producer_rejects_duplicate_keys_body_injection_and_invalid_findings(
        self,
    ):
        go = shutil.which("go")
        self.assertIsNotNone(go, "The existing Gemara test suite requires Go")
        with tempfile.TemporaryDirectory() as cache:
            env = {
                "PATH": str(Path(go).parent) + ":/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "HOME": cache,
                "GOENV": "off",
                "GOTOOLCHAIN": "local",
                "GOTELEMETRY": "off",
                "GOWORK": "off",
                "GOPROXY": "off",
                "GOSUMDB": "off",
                "GOCACHE": os.path.join(
                    tempfile.gettempdir(), "gemara-evidence-go-test-cache"
                ),
            }
            child = subprocess.run(
                [go, "test", "-count=1", "./..."],
                cwd=Path(__file__).parent / "review-evidence-producer",
                env=env,
                capture_output=True,
                timeout=120,
            )
            self.assertEqual(
                child.returncode, 0, "Native producer validation tests failed"
            )
