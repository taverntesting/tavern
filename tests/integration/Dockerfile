FROM python:3.10-alpine

RUN pip3 install pyjwt~=2.4.0 flask~=2.0.3

COPY server.py /

ENV FLASK_APP=/server.py
ENV PYTHONUNBUFFERED=0
ENV FLASK_DEBUG=1

CMD ["flask", "run", "--host=0.0.0.0"]
