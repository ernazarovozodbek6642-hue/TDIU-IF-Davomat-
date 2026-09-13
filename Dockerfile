FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tashkent \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    SELENIUM_PAGE_LOAD_TIMEOUT=45 \
    HOME=/tmp

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-noto-core \
        fonts-noto-color-emoji \
        tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && chromium --version \
    && chromedriver --version \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement requirements.txt \
    && python -m pip check

RUN groupadd --gid 10001 bot \
    && useradd --uid 10001 --gid bot --no-create-home --shell /usr/sbin/nologin bot

COPY --chown=bot:bot . .
RUN python -m compileall -q .

USER 10001:10001

HEALTHCHECK --interval=2m --timeout=20s --start-period=30s --retries=3 \
    CMD ["python", "deployment_check.py", "--local", "--quiet"]

CMD ["python", "docker_entrypoint.py"]
