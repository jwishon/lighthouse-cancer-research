# Lighthouse research worker — minimal image for a scheduled daily run.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core.py main.py ./

# Patient data and config are mounted at runtime, never baked into the image.
# Expected mounts:
#   /app/data        -> profile, idea station, digests, dedup memory (gitignored)
#   /app/config/.env -> API keys and email settings (gitignored)
ENV LIGHTHOUSE_DATA_DIR=/app/data

# Runs once and exits. Schedule it daily with cron, your host's scheduler,
# or a container scheduler. Pass an optional focus URL as an argument.
ENTRYPOINT ["python", "main.py"]
