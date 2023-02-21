FROM python:3.9-slim-buster

RUN apt-get update  && apt-get install build-essential --yes --no-install-recommends && apt-get clean
RUN pip install flask 'paho-mqtt>=1.3.1,<=1.5.1' fluent-logger 'PyYAML>=5.3.1,<6' uwsgi gevent==21.1.2

COPY server.py /

CMD ["uwsgi", "--plugin", "python3", "--http-socket", "0.0.0.0:5000", "--mount", "/=/server.py", "--gevent", "20", "--gevent-monkey-patch"]
