FROM python:3.5-slim-jessie

RUN apt-get update  && apt-get install build-essential --yes --no-install-recommends && apt-get clean
RUN pip install flask paho-mqtt fluent-logger pyyaml uwsgi gevent==1.2.2

COPY server.py /

CMD ["uwsgi", "--plugin", "python3", "--http-socket", "0.0.0.0:5000", "--mount", "/=/server.py", "--gevent", "20", "--gevent-monkey-patch"]
