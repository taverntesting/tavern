FROM python:3.5-slim-jessie

RUN pip install paho-mqtt fluent-logger pyyaml

COPY listener.py /

CMD ["python3", "/listener.py"]
