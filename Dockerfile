FROM python:3.12-alpine

RUN apk add --no-cache postgresql-dev musl-dev

WORKDIR /app

COPY . .

RUN addgroup -g 1000 gnyanamani && \
    adduser -D -u 1000 -G gnyanamani gnyanamani && \
    chown -R gnyanamani:gnyanamani /app
    
USER gnyanamani

ENV PATH="/home/gnyanamani/.local/bin:${PATH}"

RUN pip install --no-cache-dir --user poetry

RUN poetry install --no-interaction --no-ansi

CMD ["poetry","run","python","src/main.py"]