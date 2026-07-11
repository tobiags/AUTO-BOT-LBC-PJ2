import importlib.util
from pathlib import Path

import pytest


def _lab_module():
    spec = importlib.util.spec_from_file_location("experimental_lab", Path("lab/app.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_rejects_non_allowlisted_domain(monkeypatch):
    module = _lab_module()
    monkeypatch.setenv("LAB_ALLOWED_DOMAINS", "leboncoin.fr")

    with pytest.raises(ValueError, match="allowlisted"):
        module.validate_target("https://example.com")


def test_lab_classifies_browser_challenge_for_operator_intervention():
    module = _lab_module()

    assert module.classify_page("DataDome CAPTCHA", "Verify you are human") == (
        "intervention_required"
    )
