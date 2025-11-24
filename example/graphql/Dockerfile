FROM python:3.11-alpine

RUN pip3 install "strawberry-graphql[fastapi]" "uvicorn[standard]" "apsw>=3.51.0.0"

ENV PYTHONUNBUFFERED=0

COPY server.py /

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5010"]
