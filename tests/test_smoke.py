import os
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv


def test_config_loads():
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    assert cfg["retrieval"]["top_k"] > 0
    assert cfg["generation"]["model"] != cfg["judge"]["model"], "judge should differ from generator"


@pytest.mark.skipif(os.getenv("CI") == "true", reason="CI has no secrets and makes no API calls")
def test_env_present():
    load_dotenv()
    assert os.getenv("GROQ_API_KEY"), "Set GROQ_API_KEY in .env"
    assert "@" in os.getenv("SEC_USER_AGENT", ""), "Set SEC_USER_AGENT with your email in .env"