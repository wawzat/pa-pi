# Gets PurpleAir readings from PurpleAir sensor on local LAN, converts to "AQI" and displays on
# Raspberry PI with Adafruit RGB Positive LCD+Keypad Kit
# James S. Lucas - 20230720
import json
import requests
from time import sleep
import datetime
import sys
import logging
import itertools
 
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

connection_url = "http://192.168.20.36/json"


# Creates a logger
logger = logging.getLogger(__name__)  
# set log level
logger.setLevel(logging.WARNING)
# define file handler and set formatter
file_handler = logging.FileHandler('log_exception_pa_pi_rgb.log')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
# add file handler to logger
logger.addHandler(file_handler)


def retry(max_attempts=3, delay=2, escalation=10, exception=(Exception,)):
    """
    A decorator function that retries a function call a specified number of times if it raises a specified exception.

    Args:
        max_attempts (int): The maximum number of attempts to retry the function call.
        delay (int): The initial delay in seconds before the first retry.
        escalation (int): The amount of time in seconds to increase the delay by for each subsequent retry.
        exception (tuple): A tuple of exceptions to catch and retry on.

    Returns:
        The decorated function.

    Raises:
        The same exception that the decorated function raises if the maximum number of attempts is reached.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exception as e:
                    adjusted_delay = delay + escalation * attempts
                    attempts += 1
                    logger.exception(f'Error in {func.__name__}(): attempt #{attempts} of {max_attempts}')
                    if attempts < max_attempts:
                        sleep(adjusted_delay)
            logger.exception(f'Error in {func.__name__}: max of {max_attempts} attempts reached')
            print(f'Error in {func.__name__}(): max of {max_attempts} attempts reached')
            sys.exit(1)
        return wrapper
    return decorator


def write_message(Ipm25_avg, Ipm25_live, confidence, conn_success, display, active):
    """
    This function is responsible for writing a message to the LCD display.

    Args:
        Ipm25_avg (float): The average PM2.5 value.
        Ipm25_live (float): The live PM2.5 value.
        confidence (float): The confidence level of the readings.
        conn_success (bool): A flag indicating if the connection to the sensor was successful.
        display (str): A string indicating if the display is on or off.
        active (bool): A flag indicating if the sensor is active.

    Returns:
        None
    """
    if conn_success:
        if Ipm25_avg <= 50:
            health_cat = "Good"
            color = [0, 100, 0]
        elif 50 < Ipm25_avg <= 100:
            health_cat = "Moderate"
            color = [100, 100, 0]
        elif 100< Ipm25_avg <= 150:
            health_cat = "Sensitive"   
            color = [100, 100, 100]
        elif 150 < Ipm25_avg <= 200:
            health_cat = "Unhealthy"
            color = [100, 0, 0]
        elif 200 < Ipm25_avg <= 300:
            health_cat = "Very Unhealthy"
            color = [100, 0, 100]
        elif Ipm25_avg > 300:
            health_cat = "Hazardous"
            color = [0, 0, 100]
        if display == "on":
            lcd.color = color
        elif display == "off":
            lcd.clear()
            lcd.color = [0, 0, 0]
        # Calculate the number of spaces to pad between current and previous AQI
        l1_pad_length = 16 - (len(str(Ipm25_avg)) + len(str(Ipm25_live)) + 9)
        if active == True:
            online_status = next(spinner)
        else:
            online_status = ""
        l2_pad_length = 16 - (len(health_cat) + len(online_status))
        message = (
                "AQI: " + confidence + " "
                + str(Ipm25_avg)
                + ' ' * l1_pad_length
                + "L " 
                + str(Ipm25_live)
                + "\n" 
                + health_cat
                + ' ' * l2_pad_length
                + online_status
                )
    else:
        lcd.clear()
        color = [100, 0, 0]
        logger.error('Connection error')
        message = "Connection Error"
    if display == "on":
        lcd.message = message
    if message == "Connection Error":
        sleep(2)


def write_spinner(conn_success, active):
    """
    This function is used to update a spinning slash on the bottom right of the display.
    
    Parameters:
    conn_success (bool): A boolean value indicating whether the connection was successful or not.
    active (bool): A boolean value indicating whether the spinner should be active or not.

    Returns:
    None: This function does not return anything. It updates the LCD display with a spinning slash or a connection error message.
    """
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


@retry(max_attempts=4, delay=90, escalation=90, exception=(requests.exceptions.RequestException, requests.exceptions.ConnectionError))
def get_avg_reading(connection_url):
    """
    This function is used to get the average sensor reading from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    Response: A Response object containing the average sensor reading from the PurpleAir sensor.
    """
    avg_connection_string = connection_url
    avg_response = requests.get(avg_connection_string)
    return avg_response


@retry(max_attempts=4, delay=90, escalation=90, exception=(requests.exceptions.RequestException, requests.exceptions.ConnectionError))
def get_live_reading(connection_url):
    """
    This function is used to get the live sensor reading from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    Response: A Response object containing the live sensor reading from the PurpleAir sensor.
    """
    live_flag = "?live=true"
    live_connection_string = connection_url + live_flag
    live_response = requests.get(live_connection_string)
    return live_response


def process_sensor_reading(connection_url):
    """
    This function is used to process sensor readings from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    tuple: A tuple containing the average PM2.5 reading, live PM2.5 reading, confidence level, and connection success status.
    """
    avg_response = get_avg_reading(connection_url)
    live_response = get_live_reading(connection_url)
    # Parse response for printing to console
    json_response = live_response.json()
    if (avg_response.ok and live_response.ok):
        print(json.dumps(json_response, indent=4, sort_keys=True))
        avg_sensor_reading = json.loads(avg_response.text)
        live_sensor_reading = json.loads(live_response.text)
        pm2_5_reading_avg = (avg_sensor_reading['pm2_5_atm'] + avg_sensor_reading['pm2_5_atm_b']) / 2
        pm2_5_reading_live = (live_sensor_reading['pm2_5_atm'] + live_sensor_reading['pm2_5_atm_b']) / 2
        # Confidence
        # Flag if difference >= 5ug/m^3 or difference >= .7
        diff_ab = abs(avg_sensor_reading['pm2_5_atm'] - avg_sensor_reading['pm2_5_atm_b'])
        if avg_sensor_reading['pm2_5_atm'] + avg_sensor_reading['pm2_5_atm_b'] != 0:
            pct_diff_ab = (
                abs(avg_sensor_reading['pm2_5_atm'] - avg_sensor_reading['pm2_5_atm_b'])
                / (avg_sensor_reading['pm2_5_atm'] + avg_sensor_reading['pm2_5_atm_b']/2)
            )
        else:
            pct_diff_ab = 0
        if diff_ab >= 5 or pct_diff_ab >= .7:
            #This will be displayed as a "C" next to average reading instead of "A" meaning confidence issue
            confidence = 'C'
        else:
            #This will be displayed as a "A" next to average reading meaning average reading displayed (cofidence is good)
            confidence = 'A'
        conn_success = True
    else:
        print("error status code not 200")
        conn_success = False
        pm2_5_reading_avg, pm2_5_reading_live, confidence = 0, 0, 0
    return pm2_5_reading_avg, pm2_5_reading_live, confidence, conn_success


def calc_aqi(PM2_5):
    """
    This function is used to calculate the Air Quality Index (AQI) based on the PM2.5 value.

    Parameters:
    PM2_5 (float): The PM2.5 value for which the AQI is to be calculated.

    Returns:
    int: The calculated AQI value.
    """
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
        print("error in calc_aqi() function: %s" % e)


try:
    display = "on"
    active = True
    avg_reading, live_reading, confidence, conn_success = process_sensor_reading(connection_url)
    if conn_success:
        Ipm25_avg = calc_aqi(avg_reading)
    sleep(1)
    while 1:
        if (5 < datetime.datetime.now().hour <= 22) and (active == True):
            avg_reading, live_reading, confidence, conn_success = process_sensor_reading(connection_url)
            if conn_success:
                Ipm25_avg = calc_aqi(avg_reading)
                Ipm25_live = calc_aqi(live_reading)
        elif 22 < datetime.datetime.now().hour < 5:
            active = False
        write_message(Ipm25_avg, Ipm25_live, confidence, conn_success,  display, active)
        delay_loop_start = datetime.datetime.now()
        elapsed_time = datetime.datetime.now() - delay_loop_start
        #Determines refresh interval, add 2 sec to value to get actual refresh interval (+/-)
        while elapsed_time.seconds <= 3:
            elapsed_time = datetime.datetime.now() - delay_loop_start
            write_spinner(conn_success, active)
            if lcd.select_button:
                if display == "on":
                    display = "off"
                    active = False
                elif display == "off":
                    display = "on"
                    active = True
                write_message(Ipm25_avg, Ipm25_live, confidence, conn_success, display, active)
            elif lcd.right_button:
                if active == True:
                    active = False
                elif active == False:
                    active = True
                write_spinner(conn_success, active)
            sleep(.01)

except KeyboardInterrupt:
    sleep(.4)
    lcd.color = [0, 0, 0]
    lcd.message = " "
    lcd.clear()
    sleep(.4)