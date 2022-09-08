#!/usr/bin/env python3
import requests
import json
import os
import sys
#
# Use localhost & port 5000 if not specified by environment variable REST
#
REST = os.getenv("REST") or "localhost:5000"
##
# The following routine makes a JSON REST query of the specified type
# and if a successful JSON reply is made, it pretty-prints the reply
##
def mkReq(reqmethod, endpoint, data):
    print(f"Response to http://{REST}/{endpoint} request is")
    jsonData = json.dumps(data)
    response = reqmethod(f"http://{REST}/{endpoint}", data=jsonData,
                         headers={'Content-type': 'application/json'})    
    if response.status_code == 200:
        jsonResponse = json.dumps(response.json(), indent=4, sort_keys=True)
        print(jsonResponse)
        return
    else:
        print(
            f"response code is {response.status_code}, raw response is {response.text}")
        return response.text

#mkReq(requests.post, "createlisting",
#      data={
#          "mailid": "abc@gmail.com",
#          "first_name": "Abc",
#          "last_name": "Xyz",
#          "housing_type": "house",
#          "area": 1234,
#          "price": 1000,
#          "no_of_beds": 2,
#          "no_of_bath": 1.5,
#          "max_occupants": 3,
#          "address": "1838 23rd street, Boulder, Colorado 80302",
#          "start_date": "2021-01-01",
#          "end_date": "2021-06-01",
#          "pets_allowed": False
#       }
#       )

mkReq(requests.post, "updatelisting",
      data={
          "houseid": 105,
          "mailid": "saumzz19@gmail.com",
          "first_name": "Saumya",
          "last_name": "Bansal"
       }
       )

#mkReq(requests.get, "getfilteredlisting",
#      data={
#          "housing_type": "condo",
#          "area": {
#              "min": 600
#          },
#          "price": {
#              "min": 500,
#              "max": 1500
#          },
#          "bedrooms": {
#              "min": 1,
#              "max": 3
#          },
#          "bathrooms": {
#              "min": 1.5,
#              "max": 2
#          },
#          "max_occupants": {
#              "max": 3
#          },
#          "start_date":"2021-05-15",
#          "end_date":"2021-07-15",
#          "pets_allowed": "false",
# 
#          #"address": {
#          #    "zip_code": 80303
#          #},
#          
#          "close_to": "bicycle_rental"
#       }
#       )
       
#mkReq(requests.get, "getfilteredlisting",
#      data={
#          "area": 950,
#          "price": 1300
#       }
#       )

sys.exit(0)