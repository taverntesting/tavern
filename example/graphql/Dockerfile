FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

ENV PYTHONPATH=/app/
CMD ["uv", "run", "uvicorn", "tavern_graphql_example.server:app", "--host", "0.0.0.0", "--port", "5010"]
