FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

ENV PYTHONPATH=/app/
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5000", "tavern_mqtt_example.server"]
