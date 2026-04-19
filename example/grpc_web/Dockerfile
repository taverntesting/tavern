FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

WORKDIR /app
COPY . /app

RUN uv sync

ENV PYTHONPATH=.
CMD ["uv", "run", "/app/tavern_grpc_web_example/server.py"]
