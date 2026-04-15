FROM python:3.12-alpine

RUN apk add --no-cache \
    build-base \
    postgresql-dev \
    patch \
    tesseract-ocr

WORKDIR /app

COPY . .

RUN addgroup -g 1000 gnyanamani && \
    adduser -D -u 1000 -G gnyanamani gnyanamani && \
    chown -R gnyanamani:gnyanamani /app
    
USER gnyanamani

ENV PATH="/home/gnyanamani/.local/bin:${PATH}"

RUN pip install --no-cache-dir --user poetry

RUN poetry lock --no-cache --regenerate && \
    poetry install --no-interaction --no-ansi --without ocr

CMD ["poetry","run","python","src/main.py"]