FROM python:3.11-alpine

RUN pip3 install 'pyjwt>=2.4.0,<3' 'flask>=2.2.3' "python-box>=6,<7" "requests" "flask-sqlalchemy>=3,<4" "graphene-sqlalchemy>2,<3" "graphene>=3,<4" "graphql-server>=3,<4"

ENV FLASK_DEBUG=1
ENV PYTHONUNBUFFERED=0


COPY server.py /

ENV FLASK_APP=/server.py

CMD ["flask", "run", "--host=0.0.0.0"]
