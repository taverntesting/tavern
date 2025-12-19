FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

CMD ["uv", "run", "/app/tavern_mqtt_example/listener.py"]
