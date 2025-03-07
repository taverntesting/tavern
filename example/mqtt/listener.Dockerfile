FROM python:3.10-slim-buster

RUN pip install 'paho-mqtt>=1.3.1,<=1.6.1' fluent-logger 'PyYAML>=6,<7'

COPY listener.py /

CMD ["python3", "/listener.py"]
