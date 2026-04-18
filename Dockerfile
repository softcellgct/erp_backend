FROM python:3.12-alpine

RUN apk add --no-cache \
    build-base \
    postgresql-dev \
    patch \
    tesseract-ocr

WORKDIR /app

RUN addgroup -g 1000 gnyanamani && \
    adduser -D -u 1000 -G gnyanamani gnyanamani && \
    chown -R gnyanamani:gnyanamani /app

USER gnyanamani

ENV PATH="/home/gnyanamani/.local/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install --no-cache-dir --user poetry

COPY --chown=gnyanamani:gnyanamani pyproject.toml poetry.lock ./
RUN poetry install --no-ansi --without ocr --no-root

COPY --chown=gnyanamani:gnyanamani . .

CMD ["sh","-c","poetry run python main.py"]
