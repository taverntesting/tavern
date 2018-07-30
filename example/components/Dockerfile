FROM python:3.5-alpine

RUN pip install flask pyjwt

COPY server.py /

ENV FLASK_APP=/server.py

CMD ["flask", "run", "--host=0.0.0.0", "--port=5009"]
