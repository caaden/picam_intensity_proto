import time
import datetime
import picamera
import numpy as np
import cv2
import argparse
import uuid
import json
import jwt 
from tendo import singleton
import paho.mqtt.client as mqtt
import fractions

me = singleton.SingleInstance() # will sys.exit(-1) if another instance of this program is already running
token_life=60

def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=(
            'Example Google Cloud IoT Core MQTT device connection code.'))
    parser.add_argument(
            '--project_id',
            required=True,
            help='GCP cloud project name')
    parser.add_argument(
            '--registry_id', 
	    required=True, 
	    help='Cloud IoT Core registry id')
    parser.add_argument(
            '--device_id', 
	    required=True, 
	    help='Cloud IoT Core device id')
    parser.add_argument(
            '--private_key_file',
	    default='../.ssh/ec_private.pem',
            help='Path to private key file.')
    parser.add_argument(
            '--algorithm',
            choices=('RS256', 'ES256'),
            default='ES256',
            help='Which encryption algorithm to use to generate the JWT.')
    parser.add_argument(
            '--cloud_region', default='us-central1', help='GCP cloud region')
    parser.add_argument(
            '--ca_certs',
            default='/home/pi/.ssh/roots.pem',
            help=('CA root from https://pki.google.com/roots.pem'))
    parser.add_argument(
            '--mqtt_bridge_hostname',
            default='mqtt.googleapis.com',
            help='MQTT bridge hostname.')
    parser.add_argument(
            '--mqtt_bridge_port',
            choices=(8883, 443),
            default=8883,
            type=int,
            help='MQTT bridge port.')
    parser.add_argument(
            '--jwt_expires_minutes',
            default=token_life,
            type=int,
            help=('Expiration time, in minutes, for JWT tokens.'))
    return parser.parse_args()

def create_jwt(cur_time, projectID, privateKeyFilepath, algorithmType):
  token = {
      'iat': cur_time,
      'exp': cur_time + datetime.timedelta(minutes=token_life),
      'aud': projectID
  }
  with open(privateKeyFilepath, 'r') as f:
    private_key = f.read()

  return jwt.encode(token, private_key, algorithm=algorithmType) # Assuming RSA, but also supports ECC

def error_str(rc):
    return '{}: {}'.format(rc, mqtt.error_string(rc))

def on_connect(unusued_client, unused_userdata, unused_flags, rc):
    print('on_connect', error_str(rc))

def on_publish(unused_client, unused_userdata, unused_mid):
    print('on_publish')

def createJSON(timestamp, intensity):
    data = {
	'timestamp' : timestamp,
	'intensity' : intensity
    }

    json_str = json.dumps(data)
    return json_str

def main():
    args = parse_command_line_args()
    project_id = args.project_id
    gcp_location = args.cloud_region
    registry_id = args.registry_id
    device_id = args.device_id
    ssl_private_key_filepath = args.private_key_file
    ssl_algorithm = args.algorithm
    root_cert_filepath = args.ca_certs
    sensorID = registry_id + "." + device_id
    googleMQTTURL = args.mqtt_bridge_hostname
    googleMQTTPort = args.mqtt_bridge_port

    _CLIENT_ID = 'projects/{}/locations/{}/registries/{}/devices/{}'.format(project_id, gcp_location, registry_id, device_id)
    _MQTT_TOPIC = '/devices/{}/events'.format(device_id)

    with picamera.PiCamera() as camera:
        camera.resolution = (640,480)
        camera.framerate = 24
        camera.exposure_mode='off' 
        camera.awb_mode='off'
        camera.shutter_speed=4000
        camera.awb_gains=(fractions.Fraction(183, 128), fractions.Fraction(153, 128))  
        camera.contrast=0
        camera.brightness=50
        camera.sharpness=0
        camera.saturation=0
        time.sleep(2)
        
        exit=False
        while not exit:
            try:
                client = mqtt.Client(client_id=_CLIENT_ID)
                cur_time = datetime.datetime.utcnow()
                # authorization is handled purely with JWT, no user/pass, so username can be whatever
                client.username_pw_set(
                    username='unused',
                    password=create_jwt(cur_time, project_id, ssl_private_key_filepath, ssl_algorithm))
                client.on_connect = on_connect
                client.on_publish = on_publish
                client.tls_set(ca_certs=root_cert_filepath) # Replace this with 3rd party cert if that was used when creating registry
                client.connect(googleMQTTURL, googleMQTTPort)
                jwt_refresh = time.time() + ((token_life - 1) * 60) #set a refresh time for one minute before the JWT expires
                client.loop_start()
                
                # acquire image
                while time.time()<jwt_refresh:
                    output = np.empty((480, 640, 3), dtype=np.uint8) #swap x and y
                    currentTime = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') 
                    camera.capture(output, 'bgr') #open cv bgr format
                    output_gray=cv2.cvtColor(output,cv2.COLOR_BGR2GRAY)
                    intensity=np.average(output_gray)
                    print(f'[INFO] Time: {currentTime}, average intensity: {intensity:.2f}') 
                    payload = createJSON(currentTime, intensity)
                    client.publish(_MQTT_TOPIC, payload, qos=1)
                    print("{}\n".format(payload))   
                    cv2.imshow('Image',output)
                    cv2.waitKey(1000)
            except Exception as e:
                print(f"Acquisition loop stopped: {e}")
                exit=True
            
        client.loop_stop()

if __name__ == '__main__':
	main() 

