FROM python:3.11-slim-trixie

RUN python3 -m pip install uv

RUN mkdir /app
WORKDIR /app
COPY . /app

RUN uv sync

ENV PYTHONPATH=/app/

# Run as a non-root user for container security
RUN groupadd --system app && useradd --system --uid 1001 --gid app --create-home app
USER 1001
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5000", "tavern_http_example.server:app"]
