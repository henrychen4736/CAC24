FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TENNIS_MODELS_DIR=/app/models \
    TENNIS_UPLOAD_DIR=/tmp/uploads \
    PORT=8080

# mediapipe's native libs need a couple of system libraries even in headless mode
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[auth]"

# Trained artifacts (stroke_model.onnx/.json, reference_calibrated.json) if present;
# the pose model is downloaded at build time so containers start fast.
COPY models ./models
RUN tennis-ai download-models --variants heavy

EXPOSE 8080
CMD exec uvicorn tennis_ai.api.app:create_app --factory --host 0.0.0.0 --port ${PORT}
