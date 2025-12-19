FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

COPY tavern_mqtt_example/listener.py /

CMD ["uv", "run", "/listener.py"]
