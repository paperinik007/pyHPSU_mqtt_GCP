#!/usr/bin/env python3
# -*- coding: utf-8 -*-



# [START iot_mqtt_includes]
import argparse
import datetime
import logging
import os
import random
import ssl
import time

#import jwt
import json

#####
from google.cloud import pubsub_v1 as pubsub
#####

# [END iot_mqtt_includes]


import configparser
import requests
import sys
import os
import paho.mqtt.client as mqtt

algorithm='ES256' 
ca_certs='/usr/lib/python3/dist-packages/HPSU/plugins/keys/roots.pem' 
cloud_region='us-central1' 
data='Hello there' 
device_id='wio' 
gateway_id=None 
jwt_expires_minutes=1 
listen_dur=60 
message_type='event' 
mqtt_bridge_hostname='mqtt.googleapis.com' 
mqtt_bridge_port=8883 
num_messages=1 
private_key_file='/usr/lib/python3/dist-packages/HPSU/plugins/keys/ec_private.pem'
project_id='wio-cloud-335307' 
registry_id='wio-register' 
service_account_json=None 
command=None

# inserito per invio in mqtt
brokers_out={"broker1":"192.168.1.132"}




#################################################################
class export():
    hpsu = None

    def __init__(self, hpsu=None, logger=None, config_file=None):
        self.hpsu = hpsu
        self.logger = logger
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            self.config.read(self.config_file)
        else:
            sys.exit(9)

        # MQTT hostname or IP
        if self.config.has_option('invio_mqtt_gcp', 'BROKER'):
            self.brokerhost = self.config['invio_mqtt_gcp']['BROKER']
        else:
            self.brokerhost = 'localhost'

        # MQTT broker port
        if self.config.has_option('invio_mqtt_gcp', 'PORT'):
            self.brokerport = int(self.config['invio_mqtt_gcp']['PORT'])
        else:
            self.brokerport = 1883

        # MQTT client name
        if self.config.has_option('invio_mqtt_gcp', 'CLIENTNAME'):
            self.clientname = self.config['invio_mqtt_gcp']['CLIENTNAME']
        else:
            self.clientname = 'rotex'

        # MQTT Prefix
        if self.config.has_option('invio_mqtt_gcp', "PREFIX"):
            self.prefix = self.config['invio_mqtt_gcp']['PREFIX']
        else:
            self.prefix = ""

        #MQTT QOS
        if self.config.has_option('invio_mqtt_gcp',"QOS"):
            self.qos = self.config['invio_mqtt_gcp']['QOS']
        else:
            self.qos = "0"
        self.client=mqtt.Client(self.clientname)



    def pushValues(self, vars=None):

        print("************************** ")
        print("ricevuta stringa in invio_mqtt_gcp.py ")
        print("************************** ")

        stringatempo = str(datetime.datetime.now())
        stringa="{\"time\":"+"\""+stringatempo+"\""+","
        fine="}"
        h=0
        vv="\""

        for r in vars:
	
            msgs=[]

            if (h==0):
                stringa = stringa+vv+str(r['name'])+vv+":"+vv+str(r['resp'])+vv 
                h=1
            else:
                stringa=stringa+","+vv+str(r['name'])+vv+":"+vv+str(r['resp'])+vv
         
        stringa = stringa + fine 
        print("")
        print(stringa)
        print("")
        #print("ricevuta stringa e chiamato pubsub_api_call ")

        project_id = "wio-cloud-335307"
        topic_id = "topic1"

        publisher = pubsub.PublisherClient()
        topic_path = publisher.topic_path(project_id, topic_id)

        stringa_payload_bin = stringa.encode("utf-8")
        #future1 = publisher.publish(topic_path, stringa_payload_bin)
        #print(future1.result())
        #print("----- pubblicato su pubsub ------")


       	# componente necessaria alla pubblicazione su server MQTT locale
	
       	print("** pubblico dato su MQTT locale *")
	
       	topic="/home/sensors"
       	client=mqtt.Client("pythontest1")
       	print("Connecting to broker ",brokers_out["broker1"])
       	client.connect(brokers_out["broker1"])
       	client.loop_start()
       	client.subscribe(topic)
       	time.sleep(3)
       	print("sending data")
       	client.publish(topic,stringa_payload_bin)
       	time.sleep(10)
       	client.loop_stop()
       	client.disconnect()
       	print("sending mqtt ok")

