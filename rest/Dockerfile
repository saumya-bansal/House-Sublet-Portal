FROM python:3.6-slim
WORKDIR /rest
ADD . /rest
RUN pip install pika
RUN pip install flask
RUN pip install requests
RUN pip install sqlalchemy
RUN pip install psycopg2-binary
RUN pip install flask_sqlalchemy
RUN pip install httplib2
RUN pip install oauth2client
RUN pip install apiclient
CMD ["python", "rest-server.py"]