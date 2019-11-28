# Gets PurpleAir readings from API, converts to "AQI" and displays on
# Raspberry PI with Adafruit RGB Positive LCD+Keypad Kit
import json
import requests
from time import sleep
import datetime
import RPi.GPIO as GPIO
import sys
import traceback
 
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


def write_message(Ipm25):
    lcd.clear()
    if Ipm25 <= 50:
        health_cat = "Good"
        lcd.color = [0, 100, 0]
    elif 50 < Ipm25 <= 100:
        health_cat = "Moderate"
        lcd.color = [100, 100, 0]
    elif 100< Ipm25 <= 150:
        health_cat = "Sensitive"   
        lcd.color = [100, 100, 100]
    elif 150 < Ipm25 <= 200:
        health_cat = "Unhealthy"
        lcd.color = [100, 0, 0]
    elif 200 < Ipm25 <= 300:
        health_cat = "Very Unhealthy"
        lcd.color = [100, 0, 100]
    elif Ipm25 > 300:
        health_cat = "Hazardous"
        lcd.color = [0, 0, 100]
    message = "AQI: " + str(Ipm25) + "\n" + health_cat
    lcd.message = message
    return


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
        print("error in calc_aqi() function: %s") % e
        traceback.print_exc(file=sys.stdout)


sensor_id = "9208"
#sensor_id = "27815"

try:
    while 1:
        reading = get_sensor_reading(sensor_id)
        Ipm25 = calc_aqi(reading)
        write_message(Ipm25)
        delay_loop_start = datetime.datetime.now()
        elapsed_time = datetime.datetime.now() - delay_loop_start
        while elapsed_time.seconds <= 145:
            elapsed_time = datetime.datetime.now() - delay_loop_start
            sleep(.02)

except KeyboardInterrupt:
    sleep(.4)
    lcd.color = [0, 0, 0]
    lcd.clear()
    GPIO.cleanup()
