# Gets PurpleAir readings from API, converts to "AQI" and displays on
# Raspberry PI with Adafruit RGB Positive LCD+Keypad Kit
# James S. Lucas - 20200502
import json
import requests
from time import sleep
import datetime
import sys
import traceback
import itertools
import config
 
import board
import busio
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd

lcd_columns = 16
lcd_rows = 2
i2c = busio.I2C(board.SCL, board.SDA)
lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)
lcd.clear()
lcd.color = [0, 150, 0]
lcd.message = "Ready"

# Create custom backslash character
backslash = bytes([0x0,0x10,0x8,0x4,0x2,0x1,0x0,0x0])
lcd.create_char(0, backslash)

spinner = itertools.cycle(['-', '/', '|', '\x00'])

#connection_url_json = "https://www.purpleair.com/json?show="
#connection_url_rest = "https://api.purpleair.com/v1/sensors/"
connection_url_rest = "192.168.1.225/json"
sensor_id = "9208"
#sensor_id = "27815"


def write_message(Ipm25, conn_success, display, active):
    if conn_success:
        if Ipm25.get('current') <= 50:
            health_cat = "Good"
            color = [0, 100, 0]
        elif 50 < Ipm25.get('current') <= 100:
            health_cat = "Moderate"
            color = [100, 100, 0]
        elif 100< Ipm25.get('current') <= 150:
            health_cat = "Sensitive"   
            color = [100, 100, 100]
        elif 150 < Ipm25.get('current') <= 200:
            health_cat = "Unhealthy"
            color = [100, 0, 0]
        elif 200 < Ipm25.get('current') <= 300:
            health_cat = "Very Unhealthy"
            color = [100, 0, 100]
        elif Ipm25.get('current') > 300:
            health_cat = "Hazardous"
            color = [0, 0, 100]
        if display == "on":
            lcd.color = color
        elif display == "off":
            lcd.clear()
            lcd.color = [0, 0, 0]
        # Calculate the number of spaces to pad between current and previous AQI
        l1_pad_length = 16 - (len(str(Ipm25.get('current'))) + len(str(Ipm25.get('previous'))) + 8)
        if active == True:
            online_status = next(spinner)
        else:
            online_status = ""
        l2_pad_length = 16 - (len(health_cat) + len(online_status))
        message = (
                "AQI: "
                + str(Ipm25.get('current'))
                + ' ' * l1_pad_length
                + "P: "
                + str(Ipm25.get('previous'))
                + "\n" 
                + health_cat
                + ' ' * l2_pad_length
                + online_status
                )
    else:
        lcd.clear()
        color = [100, 0, 0]
        message = "Connection Error"
    if display == "on":
        lcd.message = message
    if message == "Connection Error":
        sleep(2)


def write_spinner(conn_success, display, active):
    # Updates a spinning slash on the bottom right of the display.
    if conn_success:
        if active == True:
            message = next(spinner)
        else:
            message = (" ")
        lcd.cursor_position(16,1)
    else:
        lcd.clear()
        lcd.color = [100, 0, 0]
        message = "Connection Error"
    lcd.message = message
    if message == "Connection Error":
        sleep(2)


def get_sensor_reading(sensor_id, connection_url):
    try:
        #connection_string = connection_url + sensor_id 
        connection_string = connection_url
        #header = {"X-API-Key":config.X_API_Key}
        #response = requests.get(connection_string, headers=header)
        response = requests.get(connection_string)
        if response.status_code == 200:
            print(response.text)
            sensor_reading = json.loads(response.text)
        else:
            print("error status code not 200")
            raise requests.exceptions.RequestException
        #pm2_5_reading = sensor_reading['results'][0]['PM2_5Value']
        pm2_5_reading = sensor_reading['sensor']['pm2.5_a']
        conn_success = True
        return pm2_5_reading, conn_success
    except requests.exceptions.RequestException as e:
        conn_success = False
        print("Request Exception: %s" % e)
        return 0, conn_success


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
        'sensitive': [101, 150, 33.5, 55.4],
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
        elif (33.5 <= PM2_5 <= 55.4):
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
        print("error in calc_aqi() function: %s" % e)
        traceback.print_exc(file=sys.stdout)


try:
    display = "on"
    active = True
    Ipm25 = {'current' : 0, 'previous': 0}
    reading, conn_success = get_sensor_reading(sensor_id, connection_url_rest)
    if conn_success:
        Ipm25['previous'] = calc_aqi(reading)
    sleep(1)
    while 1:
        if (5 < datetime.datetime.now().hour <= 22) and (active == True):
            reading, conn_success = get_sensor_reading(sensor_id, connection_url_rest)
            if conn_success:
                Ipm25['previous'] = Ipm25.get('current')
                Ipm25['current'] = calc_aqi(reading)
        elif 22 < datetime.datetime.now().hour < 5:
            active = False
        write_message(Ipm25, conn_success,  display, active)
        delay_loop_start = datetime.datetime.now()
        elapsed_time = datetime.datetime.now() - delay_loop_start
        while elapsed_time.seconds <= 135:
            elapsed_time = datetime.datetime.now() - delay_loop_start
            write_spinner(conn_success, display, active)
            if lcd.select_button:
                if display == "on":
                    display = "off"
                    active = False
                elif display == "off":
                    display = "on"
                    active = True
                write_message(Ipm25, conn_success, display, active)
            elif lcd.right_button:
                if active == True:
                    active = False
                elif active == False:
                    active = True
                write_spinner(conn_success, display, active)
            sleep(.01)

except KeyboardInterrupt:
    sleep(.4)
    lcd.color = [0, 0, 0]
    lcd.message = " "
    lcd.clear()
    sleep(.4)