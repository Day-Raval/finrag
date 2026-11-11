"""Run the API and UI from the repo root:  python -m finrag.app

Then open http://127.0.0.1:8000. Set PORT to change the port, and FINRAG_CONFIG
to serve another experiment config.
"""

import os

import uvicorn

# serve the final configuration unless FINRAG_CONFIG names another one
os.environ.setdefault("FINRAG_CONFIG", "configs/hdr_hf_decomp_company.yaml")

# 127.0.0.1 only: there is no authentication, and every question spends Groq tokens
uvicorn.run("finrag.app.server:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")))