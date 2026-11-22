FROM python:3.12-slim

RUN useradd --uid 10001 --create-home app
WORKDIR /app

COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir ".[service]"

USER 10001
EXPOSE 8000
CMD ["uvicorn", "coldchain.service:app", "--host", "0.0.0.0", "--port", "8000"]
