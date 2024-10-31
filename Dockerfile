FROM python:3.12
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt