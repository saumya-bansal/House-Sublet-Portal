FROM dirkcgrunwald/flair
WORKDIR /worker
ADD . /worker
RUN pip install pika
RUN pip install requests
RUN pip install sqlalchemy
RUN pip install psycopg2-binary

CMD ["python", "worker-server.py"]