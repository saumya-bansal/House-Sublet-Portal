#
# Worker server
#
import configparser
import hashlib
import io
import json
import math
import os
import pickle
import platform
import sys

import pika
import requests
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Query, scoped_session, sessionmaker

hostname = platform.node()

##
## Configure test vs. production
##
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"

print(f"Connecting to rabbitmq({rabbitMQHost})") 

db_config={}

parser = configparser.ConfigParser()
parser.read('config.ini')
for sect in parser.sections():
    if sect == "Database":
        for k,v in parser.items(sect):
            db_config[k] = v

url = 'postgresql://' + db_config['user'] + ':' + db_config['password'] + '@' + db_config['host'] + ":" + db_config['port'] + '/' + db_config['db_name']
     
engine = create_engine(url, convert_unicode=True, echo=False)
Base = declarative_base()
Base.metadata.reflect(engine)

class Amenities(Base):
    __table__ = Base.metadata.tables['amenities']

##
## Set up rabbitmq connection
##
def getMQ():
    parameters = (
    pika.ConnectionParameters(host=rabbitMQHost)
    )
    rabbitMQ = pika.BlockingConnection(parameters)
    rabbitMQChannel = rabbitMQ.channel()
    rabbitMQChannel.exchange_declare(exchange='logs', exchange_type='topic')
    rabbitMQChannel.queue_declare(queue='toWorker')
    return rabbitMQChannel

infoKey = f"{platform.node()}.worker.info"
debugKey = f"{platform.node()}.worker.debug"

def log_debug(message, key=debugKey):
    print("DEBUG:", message, file=sys.stdout)
    with getMQ() as mq:
        mq.basic_publish(
        exchange='logs', routing_key=key, body=message)

def log_info(message, key=infoKey):
    print("INFO:", message, file=sys.stdout)
    with getMQ() as mq:
        mq.basic_publish(
        exchange='logs', routing_key=key, body=message)


##
## Your code goes here...
##
def callback(ch, method, properties, body):
    body = json.loads((body.decode("utf-8")))
    lat = body['latitude']
    lon = body['longitude']
    listing_id = body['listing_id']
    bounding_box = get_bounding_rectangle(lat, lon, 3)
    coordinate_string = "(" + str(bounding_box[0] * 180 / math.pi) + "," +  str(bounding_box[1] * 180 / math.pi) + "," + str(bounding_box[2] * 180 / math.pi) + "," + str(bounding_box[3] * 180 / math.pi) + ");\n"
    bicycle_rental_names = get_amenity_list("bicycle_rental", coordinate_string)
    university_names = get_amenity_list("university", coordinate_string)
    cafe_names = get_amenity_list("cafe", coordinate_string)
    market_names = get_amenity_list("marketplace", coordinate_string)
    
    #Write to database
    print(type(university_names))
    db_session = scoped_session(sessionmaker(bind=engine))
    new_amenity_list = Amenities(
        listing_id = listing_id,
        cafes = cafe_names if cafe_names else None,
        bicycle_rentals = bicycle_rental_names if bicycle_rental_names else None,
        universities  = university_names if university_names else None,
        marketplaces = market_names if market_names else None
    )

    db_session.add(new_amenity_list)
    db_session.commit()

    ch.basic_ack(delivery_tag=method.delivery_tag)

def get_amenity_list(amenity_name, coordinate_string):
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query="[out:json];\n node\n [\"amenity\"=\"" + amenity_name + "\"]\n" + coordinate_string + "out;\n out center;"
    response = requests.get(overpass_url,
                        params={'data': overpass_query})
    amenities = (response.json()["elements"])
    amenities_list=[]
    for amenity in amenities:
        try:
            amenities_list.append(amenity['tags']['name'])
        except:
            # Do nothing
            continue
    amenity_names = ','.join(list(set(amenities_list)))
    return amenity_names


def get_bounding_rectangle(lat, lon, dist):
    r =  dist/6371
    lat = lat * math.pi / 180
    lon = lon * math.pi / 180
    latmin =  lat - r
    latmax = lat + r
    latT = math.asin(math.sin(lat)/math.cos(r))
    deltalon = math.acos((math.cos(r)-math.sin(latT) * math.sin(lat))/ (math.cos(latT) * math.cos(lat)))
    lonmin = lon - deltalon
    lonmax = lon + deltalon
    return [latmin, lonmin, latmax, lonmax]

with getMQ() as mq:
    mq.basic_consume(queue='toWorker', on_message_callback=callback, auto_ack=False)
    log_info("Worker running")
    mq.start_consuming()
