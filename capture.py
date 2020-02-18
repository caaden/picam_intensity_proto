import time
import picamera
import numpy as np
import cv2
#import argparse


with picamera.PiCamera() as camera:
    camera.resolution = (640,480)
    camera.framerate = 24
    time.sleep(2)
    while True:   
        output = np.empty((480, 640, 3), dtype=np.uint8) #swap x and y
        camera.capture(output, 'bgr') #open cv bgr format
        output_gray=cv2.cvtColor(output,cv2.COLOR_BGR2GRAY)
        intensity=np.average(output)
        print(f'[INFO] Time: {time.time()}, average intensity: {intensity:.2f}') 
        cv2.imshow('Image',output)
        cv2.waitKey(1000)