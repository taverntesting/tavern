FROM python:3.9-slim-buster

RUN pip install 'paho-mqtt>=1.3.1,<=1.5.1' fluent-logger 'PyYAML>=5.3.1,<6'

COPY listener.py /

CMD ["python3", "/listener.py"]
