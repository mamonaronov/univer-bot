FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Moscow \
    TELEGRAM_PROXY_URL=socks5://127.0.0.1:11808

WORKDIR /app

ARG MIHOMO_VERSION=v1.19.30
ARG TARGETARCH=amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gzip \
        gosu \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && gosu nobody true \
    && if [ "$TARGETARCH" = "amd64" ]; then \
         MIHOMO_FILE="mihomo-linux-amd64-compatible-${MIHOMO_VERSION}.gz"; \
       else \
         MIHOMO_FILE="mihomo-linux-${TARGETARCH}-${MIHOMO_VERSION}.gz"; \
       fi \
    && curl -fsSL -o /tmp/mihomo.gz \
         "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/${MIHOMO_FILE}" \
    && gunzip -c /tmp/mihomo.gz > /usr/local/bin/mihomo \
    && chmod +x /usr/local/bin/mihomo \
    && rm /tmp/mihomo.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY deploy/mihomo/config.yaml /app/mihomo/config.yaml

RUN useradd --create-home --uid 1000 botuser \
    && mkdir -p /app/data /app/mihomo/providers \
    && chown -R botuser:botuser /app \
    && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
