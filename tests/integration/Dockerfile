FROM python:3.5-alpine

RUN pip install flask pyjwt

COPY server.py /

ENV FLASK_APP=/server.py
ENV PYTHONUNBUFFERED=0
ENV FLASK_DEBUG=1

CMD ["flask", "run", "--host=0.0.0.0"]
