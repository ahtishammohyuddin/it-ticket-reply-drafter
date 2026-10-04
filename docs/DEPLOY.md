# Deploy the live demo for free

## Streamlit Community Cloud (free, used for the live demo)

The repo includes `streamlit_app.py`, a front end that runs the same pipeline as the FastAPI service (redaction, signals, retrieval, drafting, guardrails). Streamlit Community Cloud hosts it for free from your public GitHub repo.

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Repository: `ahtishammohyuddin/it-ticket-reply-drafter`. Branch: `main`. Main file path: `streamlit_app.py`.
4. App URL: choose something like `it-ticket-reply-drafter`.
5. Open **Advanced settings**. Python version: **3.12**. In **Secrets**, paste:

```
GEMINI_API_KEY = "your-key-here"
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

6. Click **Deploy**. The first build takes a few minutes.

Secrets are never visible to visitors or in the repo. Apps sleep after a few days without visitors and wake when someone opens the link, so open it yourself before sending it to a company.

## FastAPI service with Docker (for a real deployment)

The FastAPI app (`app/main.py`, served with uvicorn) and the `Dockerfile` are the production shape: a JSON API plus the agent console in `static/index.html`. Run it locally with `uvicorn app.main:app`, or with Docker:

```
docker build -t ticket-drafter .
docker run -p 7860:7860 --env-file .env ticket-drafter
```

Any host that runs a Docker container can serve it. Free Docker hosting changes often, so the live demo uses Streamlit Community Cloud instead.
