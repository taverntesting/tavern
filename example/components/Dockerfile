FROM python:3.9-alpine

RUN pip install flask

RUN pip install pyjwt>=2.4.0,<3

COPY server.py /

ENV FLASK_APP=/server.py

CMD ["flask", "run", "--host=0.0.0.0", "--port=5009"]
