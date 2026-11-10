FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ia ./ia
COPY harness ./harness
COPY prompts ./prompts

RUN useradd --create-home --uid 10001 agente
USER agente

CMD ["python", "-m", "harness.worker"]
