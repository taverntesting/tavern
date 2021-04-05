FROM python:3.9-slim-buster

RUN pip install paho-mqtt fluent-logger pyyaml

COPY listener.py /

CMD ["python3", "/listener.py"]
