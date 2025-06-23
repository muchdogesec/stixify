FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt

COPY install_deps.sh .
RUN --mount=type=cache,target=/var/cache/apt/archives/ \
    bash install_deps.sh

