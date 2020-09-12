# Gets readings from PurpleAir API, converts to "AQI" and displays
# on Raspberry Pi with Adafruit 128x64 OLED Bonnet
import json
import requests
from time import sleep
import pytz, datetime
import RPi.GPIO as GPIO
import sys
import traceback

# import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# Raspberry Pi pin configuration:
RST = None     # on the PiOLED this pin isn't used

# 128x64 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)

# Initialize library.
disp.begin()

# Clear display.
disp.clear()
disp.display()
sleep(.1)

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load default font.
# font = ImageFont.load_default()

# Or alternatively load a TTF font.  Make sure the .ttf font file is in the same directory as the python script.
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
# JSL Load Custom Fonts
font14 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 14)
font16 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 16)
font17 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 17)
font18 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 18)
font20 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 20)
font22 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 22)
font24 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 24)
font26 = ImageFont.truetype('VCR_OSD_MONO_1.001.ttf', 26)

draw.text((x, 18),      "Initializing", font=font17, fill=255)
# Display image.
disp.image(image)
disp.display()
sleep(.1)


def write_message(reading):
    disp.clear()
    disp.display()
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((x, 24),        "AQI: " + reading, font=font26, fill=255)
    #draw.text((x, 18),        messages[1], font=font18, fill=255)
    #draw.text((x, 24),        messages[3], font=font14, fill=255)
    # draw.text((x, 48),        messages[4], font=font18, fill=255)
    # Display image.
    disp.image(image)
    disp.display()
    sleep(.05)


def get_sensor_reading(sensor_id):
    response = requests.get("https://www.purpleair.com/json?show=" + sensor_id)
    sensor_reading = json.loads(response.text)
    pm2_5_reading = sensor_reading['results'][0]['PM2_5Value']
    return pm2_5_reading


def calc_aqi(PM2_5):
    # Function takes the instantaneous PM2.5 value and calculates
    # "AQI". "AQI" in quotes as this is not an official methodology. AQI is
    # 24 hour midnight-midnight average. May change to NowCast or other
    # methodology in the future.

    # Truncate to one decimal place.
    PM2_5 = int(float(PM2_5) * 10) / 10.0
    if PM2_5 < 0:
        PM2_5 = 0
    #AQI breakpoints [0,    1,     2,    3    ]
    #                [Ilow, Ihigh, Clow, Chigh]
    pm25_aqi = {
        'good': [0, 50, 0, 12],
        'moderate': [51, 100, 12.1, 35.4],
        'sensitive': [101, 150, 35.5, 55.4],
        'unhealthy': [151, 200, 55.5, 150.4],
        'very': [201, 300, 150.5, 250.4],
        'hazardous': [301, 500, 250.5, 500.4],
        'beyond_aqi': [301, 500, 250.5, 500.4]
        }
    try:
        if (0.0 <= PM2_5 <= 12.0):
            aqi_cat = 'good'
        elif (12.1 <= PM2_5 <= 35.4):
            aqi_cat = 'moderate'
        elif (35.5 <= PM2_5 <= 55.4):
            aqi_cat = 'sensitive'
        elif (55.5 <= PM2_5 <= 150.4):
            aqi_cat = 'unhealthy'
        elif (150.5 <= PM2_5 <= 250.4):
            aqi_cat = 'very'
        elif (250.5 <= PM2_5 <= 500.4):
            aqi_cat = 'hazardous'
        elif (PM2_5 >= 500.5):
            aqi_cat = 'beyond_aqi'
        else:
            print(" ")
            print("PM2_5: " + str(PM2_5))
        Ihigh = pm25_aqi.get(aqi_cat)[1]
        Ilow = pm25_aqi.get(aqi_cat)[0]
        Chigh = pm25_aqi.get(aqi_cat)[3]
        Clow = pm25_aqi.get(aqi_cat)[2]
        Ipm25 = int(round(
            ((Ihigh - Ilow) / (Chigh - Clow) * (PM2_5 - Clow) + Ilow)
            ))
        return Ipm25
    except Exception as e:
        pass
        print("error in calc_aqi() function: %s") % e
	traceback.print_exc(file=sys.stdout)


sensor_id = "9208"

try:
    while 1:
        reading = get_sensor_reading(sensor_id)
        Ipm25 = calc_aqi(reading)
        write_message(str(Ipm25))
        delay_loop_start = datetime.datetime.now()
        elapsed_time = datetime.datetime.now() - delay_loop_start
        while elapsed_time.seconds <= 45:
            elapsed_time = datetime.datetime.now() - delay_loop_start
            sleep(.02)

except KeyboardInterrupt:
   disp.clear()
   disp.display()
   draw.rectangle((0,0,width,height), outline=0, fill=0)
   sleep(.4)
   GPIO.cleanup()
