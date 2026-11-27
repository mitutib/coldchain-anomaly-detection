FROM python:3.12-slim

RUN useradd --uid 10001 --create-home app
WORKDIR /app

# Dependencies are read from pyproject.toml and installed before the source is
# copied, so this layer is rebuilt only when pyproject.toml changes.
COPY pyproject.toml .
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['optional-dependencies']['service']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY src src
RUN pip install --no-cache-dir --no-deps .

USER 10001
EXPOSE 8000
CMD ["uvicorn", "coldchain.service:app", "--host", "0.0.0.0", "--port", "8000"]
