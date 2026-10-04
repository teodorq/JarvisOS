from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_business_public_api_loads_services_only_when_requested() -> None:
    source = """
import sys
import app.business as business
assert 'app.business.business_config' not in sys.modules
assert 'app.business.business_edition_service' not in sys.modules
assert business.BusinessConfigStore.__name__ == 'BusinessConfigStore'
assert 'app.business.business_config' in sys.modules
assert 'app.business.business_edition_service' not in sys.modules
assert business.BusinessEditionService.__name__ == 'BusinessEditionService'
assert 'app.business.business_edition_service' in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_business_public_api_still_supports_from_import() -> None:
    from app.business import BusinessConfigStore, BusinessLicenseManager

    assert BusinessConfigStore.__name__ == "BusinessConfigStore"
    assert BusinessLicenseManager.__name__ == "BusinessLicenseManager"
