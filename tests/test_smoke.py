import os

import yaml
from dotenv import load_dotenv


def test_config_loads():
    cfg = yaml.safe_load(open("config.yaml"))
    assert cfg["retrieval"]["top_k"] > 0
    assert cfg["generation"]["model"] != cfg["judge"]["model"], "judge should differ from generator"


def test_env_present():
    load_dotenv()
    assert os.getenv("GROQ_API_KEY"), "Set GROQ_API_KEY in .env"
    assert "@" in os.getenv("SEC_USER_AGENT", ""), "Set SEC_USER_AGENT with your email in .env"
