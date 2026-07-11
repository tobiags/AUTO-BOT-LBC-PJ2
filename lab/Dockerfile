FROM python:3.12-slim

ARG OBSCURA_VERSION=latest
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /lab
COPY lab/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m camoufox fetch \
    && curl -fsSL "https://github.com/h4ckf0r0day/obscura/releases/${OBSCURA_VERSION}/download/obscura-x86_64-linux.tar.gz" \
      -o /tmp/obscura.tar.gz \
    && tar -xzf /tmp/obscura.tar.gz -C /usr/local/bin \
    && chmod +x /usr/local/bin/obscura \
    && rm /tmp/obscura.tar.gz

COPY lab/app.py ./app.py
RUN useradd --create-home --uid 10001 labuser \
    && mkdir -p /runtime/camoufox /runtime/obscura /runtime/reports \
    && chown -R labuser:labuser /runtime
USER labuser

ENV LAB_ALLOWED_DOMAINS=www.leboncoin.fr,leboncoin.fr
EXPOSE 8010
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
