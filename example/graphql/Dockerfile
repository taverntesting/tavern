FROM python:3.14-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

ENV PYTHONPATH=/app/

# Run as a non-root user for container security
RUN groupadd --system app && useradd --system --uid 1001 --gid app --create-home app
USER 1001
CMD ["uv", "run", "uvicorn", "tavern_graphql_example.server:app", "--host", "0.0.0.0", "--port", "5010"]
