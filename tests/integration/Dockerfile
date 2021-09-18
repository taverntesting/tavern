FROM python:3.9-alpine

RUN pip install flask 'pyjwt>=1.7.1,<2'

COPY server.py /
RUN mkdir examples
COPY examples /examples/

ENV FLASK_APP=/server.py
ENV PYTHONUNBUFFERED=0
ENV FLASK_DEBUG=1

CMD ["flask", "run", "--host=0.0.0.0"]
