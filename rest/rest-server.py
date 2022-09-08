from __future__ import print_function

import ast
import base64
import hashlib
import io
import json
import mimetypes
import os
import platform
import sys
from base64 import urlsafe_b64encode
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httplib2
import oauth2client
import pika
import requests
from apiclient import discovery, errors
from apiclient.discovery import build
from flask import Flask, Response, jsonify, request
from flask_sqlalchemy import sqlalchemy
from google.oauth2 import service_account
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import client, file, tools
from sqlalchemy import create_engine, func, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (Query, backref, relationship, scoped_session,
                            sessionmaker)
from sqlalchemy.sql.expression import null
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.util.langhelpers import assert_arg_type

app = Flask(__name__)
app.config.from_pyfile('../config/app.conf')
user = app.config.get("USER")
password = app.config.get("PASSWORD")
host = app.config.get("HOST")
port = app.config.get("PORT")
db_name = app.config.get("DB_NAME")
google_api_key = app.config.get("GOOGLE_API_KEY")
sender_mailid = "housesubletportal@gmail.com"

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Gmail API Python Send Email'

url = 'postgresql://' + user + ':' + password + '@' + host + ":" + port + '/' + db_name
engine = create_engine(url, convert_unicode=True, echo=False)
Base = declarative_base()
Base.metadata.reflect(engine)

class HouseDetails(Base):
    __table__ = Base.metadata.tables['house_details']

class Sublessee(Base):
    __table__ = Base.metadata.tables['sublessee']

class Sublessor(Base):
    __table__ = Base.metadata.tables['sublessor']

class Amenities(Base):
    __table__ = Base.metadata.tables['amenities']

##
## Configure test vs. production
##
rabbitMQHost = os.getenv("RABBITMQ_HOST") or "localhost"
print("Connecting to rabbitmq({})".format(rabbitMQHost))
##
## Your code goes here..
##
    
def getMQ():
    parameters = (
    pika.ConnectionParameters(host=rabbitMQHost, port=5672)
    )
    rabbitMQ = pika.BlockingConnection(parameters)
    rabbitMQChannel = rabbitMQ.channel()
    rabbitMQChannel.exchange_declare(exchange='logs', exchange_type='topic')
    rabbitMQChannel.queue_declare(queue='toWorker')
    return rabbitMQChannel

infoKey = f"{platform.node()}.worker.info"
debugKey = f"{platform.node()}.worker.debug"
#
# A helpful function to send a log message
#
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


@app.route('/createlisting', methods=['POST'])
def create_listing():
    json_data = request.get_json()
    db_session = scoped_session(sessionmaker(bind=engine))
    # for item in db_session.query(HouseDetails.price, HouseDetails.listing_id):
    #     print(item)
    sublessorid = coalesce(db_session.query(func.max(Sublessor.sublessorid))[0][0],0) + 1
    new_sublessor=Sublessor(
        sublessorid=sublessorid,
        mailid = json_data['mailid'],
        first_name = json_data['first_name'],
        last_name = json_data['last_name']
    )
    db_session.add(new_sublessor)
    listingid = coalesce(db_session.query(func.max(HouseDetails.listingid)).all()[0][0],0) + 1
    coordinates = extract_lat_long_via_address(json_data['address'])
    new_housedetails=HouseDetails(
        listingid=listingid,
        housing_type = json_data['housing_type'],
        area = json_data['area'],
        price = json_data['price'],
        no_of_beds = json_data['no_of_beds'],
        no_of_bath = json_data['no_of_bath'],
        max_occupants = json_data['max_occupants'],
        address = json_data['address'],
        start_date = json_data['start_date'],
        end_date = json_data['end_date'],
        latitude=coordinates[0],
        longitude = coordinates[1],
        pets_allowed = json_data['pets_allowed'],
        sublessorid = sublessorid,
        booked= False
    )
    db_session.add(new_housedetails)
    db_session.commit()
    response = {'Action':'Listing created'}

    json_data['listing_id'] = listingid
    json_data['latitude'] = coordinates[0]
    json_data['longitude'] = coordinates[1]

    formattedJson = json.dumps(json_data)
    with getMQ() as mq:
        mq.basic_publish(exchange='',routing_key='toWorker', body=formattedJson)
    
    log_info("Input: " + formattedJson + " Output" + json.dumps(response))
    return Response(json.dumps(response), status=200, mimetype="application/json")

def extract_lat_long_via_address(address_or_zipcode):
    latitude, longitude = None, None
    api_key = google_api_key
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    endpoint = f"{base_url}?address={address_or_zipcode}&key={api_key}"
    r = requests.get(endpoint)
    if r.status_code not in range(200, 299):
        return None, None
    try:
        '''
        This try block incase any of our inputs are invalid. This is done instead
        of actually writing out handlers for all kinds of responses.
        '''
        results = r.json()['results'][0]
        latitude = results['geometry']['location']['lat']
        longitude = results['geometry']['location']['lng']
    except:
        pass
    return latitude, longitude

    
@app.route('/updatelisting', methods=['POST'])
def update_listing():
    json_data = request.get_json()
    formattedJson = json.dumps(json_data)
    with getMQ() as mq:
        mq.basic_publish(exchange='',routing_key='toWorker', body=formattedJson)
    db_session = scoped_session(sessionmaker(bind=engine))
    # for item in db_session.query(HouseDetails.price, HouseDetails.listing_id):
    #     print(item)
    sublesseeid = coalesce(db_session.query(func.max(Sublessee.sublesseeid))[0][0],0) + 1
    new_sublessee=Sublessee(
    sublesseeid = sublesseeid,
    mailid = json_data['mailid'],
    first_name = json_data['first_name'],
    last_name = json_data['last_name']
    )

    db_session.add(new_sublessee)
    houseid=json_data['houseid']
    conn=engine.connect()
    query = update(HouseDetails).where(HouseDetails.listingid==houseid).values(sublesseeid=sublesseeid, booked=True)
    conn.execute(query)
    db_session.commit()

    sender = sender_mailid
    to = new_sublessee.mailid
    subject = "Booking confirmed"
    message = "Hi " + new_sublessee.first_name + " " + new_sublessee.last_name + ",\n\nCongratulations! You have successfully booked House No " + str(houseid) + ".\n\nRegards,\nSASA Sublets"
    
    result = SendMessage(sender, to, subject, message)
    print(result)

    response = {'Action':'Listing updated'}
    log_info("Input: " + formattedJson + " Output" + json.dumps(response))
    return Response(json.dumps(response), status=200, mimetype="application/json")

def SendMessage(sender, to, subject, message):
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    message = CreateMessageHtml(sender, to, subject, message)
    result = SendMessageInternal(service, "me", message)
    return result

def get_credentials():
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,'.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, ' '.join(SCOPES))
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def CreateMessageHtml(sender, to, subject, message_text):
    """Create a message for an email.
    Args:
        sender: Email address of the sender.
        to: Email address of the receiver.
        subject: The subject of the email message.
        message_text: The text of the email message.
    Returns:
        An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

def SendMessageInternal(service, user_id, message):
    try:
        message = (service.users().messages().send(userId=user_id, body=message).execute())
        print('Message Id: %s' % message['id'])
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)
        return "Error"


@app.route('/getfilteredlisting', methods=['GET'])
def get_filtered_listing():

    arguments = request.get_json()
    filters_list = []
    db_session = scoped_session(sessionmaker(bind=engine))

    for filters in arguments.keys():
        filters_list.append(filters)

    if "close_to" in filters_list:
        query = db_session.query(HouseDetails, Amenities)
        close_to = arguments["close_to"]
        values = close_to.strip().split(",")
        query = query.filter(HouseDetails.listingid == Amenities.listing_id)
        if "cafe" in values:
           query = query.filter(Amenities.cafes != None)
        if "university" in values:
           query = query.filter(Amenities.universities != None)
        if "marketplace" in values:
           query = query.filter(Amenities.marketplaces != None) 
        if "bicycle_rental" in values:
           query = query.filter(Amenities.bicycle_rentals != None)
    
    else:
        query = db_session.query(HouseDetails)

    if "housing_type" in filters_list:
        housing_type = arguments["housing_type"]
        query = query.filter(HouseDetails.housing_type == housing_type)

    if "area" in filters_list:
        area = arguments["area"]
        keys = []
        try:
            for key in area.keys():
                keys.append(key)
            if "min" in keys:
                 query = query.filter(HouseDetails.area >=  area["min"])
            if "max" in keys:
                 query= query.filter(HouseDetails.area <= area["max"])
        except AttributeError:
            query = query.filter(HouseDetails.area == str(area))

    if "price" in filters_list:
        price = arguments["price"]
        keys = []
        try:
            for key in price.keys():
                keys.append(key)
            if "min" in keys:
                query =  query.filter(HouseDetails.price >=  price["min"])
            if "max" in keys:
                query = query.filter(HouseDetails.price <=  price["max"])
        except AttributeError:
                query = query.filter(HouseDetails.price == str(price))

    if "bedrooms" in filters_list:
        bedrooms = arguments["bedrooms"]
        keys = []
        try:
            for key in bedrooms.keys():
                keys.append(key)
            if "min" in keys:
                 query = query.filter(HouseDetails.no_of_beds >=  bedrooms["min"])
            if "max" in keys:
                 query= query.filter(HouseDetails.no_of_beds <= bedrooms["max"])
        except AttributeError:
            query = query.filter(HouseDetails.no_of_beds == str(bedrooms))

    if "bathrooms" in filters_list:
        bath = arguments["bathrooms"]
        keys = []
        try:
            for key in bath.keys():
                keys.append(key)
            if "min" in keys:
                 query = query.filter(HouseDetails.no_of_bath >=  bath["min"])
            if "max" in keys:
                 query= query.filter(HouseDetails.no_of_bath <= bath["max"])
        except AttributeError:
            query = query.filter(HouseDetails.no_of_bath == str(bath))

    if "max_occupants" in filters_list:
        max_occupants = arguments["max_occupants"]
        keys = []
        try:
            for key in max_occupants.keys():
                keys.append(key)
            if "min" in keys:
                 query = query.filter(HouseDetails.max_occupants >=  max_occupants["min"])
            if "max" in keys:
                 query= query.filter(HouseDetails.max_occupants <= max_occupants["max"])
        except AttributeError:
            query = query.filter(HouseDetails.max_occupants == str(max_occupants))

    if "start_date" in filters_list:
        start_date = arguments["start_date"]
        query = query.filter(HouseDetails.start_date == start_date)

    if "end_date" in filters_list:
        end_date = arguments["end_date"]
        query = query.filter(HouseDetails.end_date == end_date)

    if "pets_allowed" in filters_list:
        pets_allowed = arguments["pets_allowed"]
        query = query.filter(HouseDetails.pets_allowed == pets_allowed)
    
    if "address" in filters_list:
        address = arguments["address"]
        keys=[]
        try:
            for key in address.keys():
                keys.append(key)
            if "zip_code" in keys:
                search = "% {}".format(str(address["zip_code"]))
                query = query.filter(HouseDetails.address.like(search))
            if "state" in keys:
                 query= query.filter(HouseDetails.address.ilike("% " + address["state"] + " %"))
        except AttributeError:
            query = query.filter(HouseDetails.address == address)

        
    query = query.filter(HouseDetails.booked == "false")
    response_list = {}

    if "close_to" not in filters_list:
        results = query.all()
        for result in results:
            dictionary = {"Housing type": result.housing_type, "Area": result.area, "Price": result.price, "Number of bedrooms": result.no_of_beds,
            "No of bathrooms": result.no_of_bath, "Maximum occupants": result.max_occupants, "Address":  result.address,
            "Start date": str(result.start_date), "End date": str(result.end_date), "Pets allowed": result.pets_allowed}
            response_list[result.listingid] = dictionary
    else:
        for result, amenities in query.all():
            dictionary = {"Housing type": result.housing_type, "Area": result.area, "Price": result.price, "Number of bedrooms": result.no_of_beds,
            "No of bathrooms": result.no_of_bath, "Maximum occupants": result.max_occupants, "Address":  result.address,
            "Start date": str(result.start_date), "End date": str(result.end_date), "Pets allowed": result.pets_allowed, "Cafes nearby": amenities.cafes,
            "Universities nearby": amenities.universities, "Marketplaces nearby": amenities.marketplaces, "Bicycle rentals nearby": amenities.bicycle_rentals}
            response_list[result.listingid] = dictionary

    return Response(json.dumps(response_list), status=200, mimetype="application/json")

# start flask app
app.run(host="0.0.0.0", port=5000, debug = True)
