# Gets PurpleAir readings from PurpleAir sensor on local LAN, converts to "AQI" and displays on
# Raspberry PI with Adafruit RGB Positive LCD+Keypad Kit
# James S. Lucas - 20230722
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


def retry(max_attempts=15, delay=2, escalation=2, exception=(Exception,)):
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
            exit_handler()
        return wrapper
    return decorator


def write_message(Ipm25_avg, Ipm25_live, avg_confidence, live_confidence, conn_success, display, active):
    """
    This function writes a message to the LCD display.

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
        aqi_categories = (
            (50, "Good", [0, 100, 0]),
            (100, "Moderate", [100, 100, 0]),
            (150, "Sensitive", [100, 100, 100]),
            (200, "Unhealthy", [100, 0, 0]),
            (300, "Very Unhealthy", [100, 0, 100]),
            (float('inf'), "Hazardous", [0, 0, 100])
        )
        for limit, category, color_value in aqi_categories:
            if Ipm25_avg <= limit:
                aqi_cat = category
                color = color_value
                break
        if display == "on":
            lcd.color = color
        elif display == "off":
            lcd.clear()
            lcd.color = [0, 0, 0]
        # Calculate the number of spaces to pad between average and live AQI
        l1_pad_length = 16 - (len(str(Ipm25_avg)) + len(str(Ipm25_live)) + 9)
        if active == True:
            online_status = next(spinner)
        else:
            online_status = ""
        l2_pad_length = 16 - (len(aqi_cat) + len(online_status))
        message = (
                "AQI: A" + avg_confidence
                + str(Ipm25_avg)
                + ' ' * l1_pad_length
                + "L" + live_confidence
                + str(Ipm25_live)
                + "\n" 
                + aqi_cat
                + ' ' * l2_pad_length
                + online_status
                )
    else:
        lcd.clear()
        color = [100, 0, 0]
        logger.error('write_message() connection error')
        message = "Connection Error"
    if display == "on":
        lcd.message = message
    if message == "Connection Error":
        sleep(2)


def write_spinner(conn_success, active):
    """
    This function updates a spinning slash on the bottom right of the display.
    
    Parameters:
    conn_success (bool): A boolean value indicating whether the connection was successful or not.
    active (bool): A boolean value indicating whether the spinner should be active or not.

    Returns:
    None: This function does not return anything. It updates the LCD display with a spinning slash or a connection error message.
    """
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


@retry(max_attempts=15, delay=2, escalation=2, exception=(requests.exceptions.RequestException, requests.exceptions.ConnectionError))
def get_avg_reading(connection_url):
    """
    This function gets the average sensor reading from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    Response: A Response object containing the average sensor reading from the PurpleAir sensor.
    """
    avg_connection_string = connection_url
    avg_response = requests.get(avg_connection_string)
    return avg_response


@retry(max_attempts=15, delay=2, escalation=2, exception=(requests.exceptions.RequestException, requests.exceptions.ConnectionError))
def get_live_reading(connection_url):
    """
    This function gets the live sensor reading from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    Response: A Response object containing the live sensor reading from the PurpleAir sensor.
    """
    live_flag = "?live=true"
    live_connection_string = connection_url + live_flag
    live_response = requests.get(live_connection_string)
    return live_response



def confidence_check(sensor_response):
    """
    This function checks the confidence of the sensor readings from a PurpleAir sensor.
    The confidence is determined based on the difference between the two sensor readings.
    If the difference is greater than or equal to 5ug/m^3 or the percentage difference is greater than or equal to 0.7,
    the confidence is flagged as low (represented by 'c'). Otherwise, the confidence is considered good (represented by ' ').

    Parameters:
    sensor_response (Response): The response object containing the sensor readings from the PurpleAir sensor.

    Returns:
    str: A string representing the confidence of the sensor readings.
    The string is used on the display. 'c' is displayed for low confidence and blank ' ' for good confidence.
    """
    sensor_reading = json.loads(sensor_response.text)
    # Confidence
    # Flag if difference >= 5ug/m^3 or difference >= .7
    diff_ab = abs(sensor_reading['pm2_5_atm'] - sensor_reading['pm2_5_atm_b'])
    if sensor_reading['pm2_5_atm'] + sensor_reading['pm2_5_atm_b'] != 0:
        pct_diff_ab = (
            abs(sensor_reading['pm2_5_atm'] - sensor_reading['pm2_5_atm_b'])
            / (sensor_reading['pm2_5_atm'] + sensor_reading['pm2_5_atm_b']/2)
        )
    else:
        pct_diff_ab = 0
    if diff_ab >= 5 or pct_diff_ab >= .7:
        # This will be displayed as a "c" next to the average or live reading to flag low confidence.
        confidence = 'c'
    else:
        # Confidence is good
        confidence = ' '
    return confidence


def process_sensor_reading(connection_url):
    """
    This function processes sensor readings from a PurpleAir sensor.

    Parameters:
    connection_url (str): The URL of the PurpleAir sensor.

    Returns:
    tuple: A tuple containing the average PM2.5 reading, live PM2.5 reading, confidence level, and connection success status.
    """
    avg_response = get_avg_reading(connection_url)
    live_response = get_live_reading(connection_url)
    if (avg_response.ok and live_response.ok):
        conn_success = True
        #json_response = live_response.json()
        #print(json.dumps(json_response, indent=4, sort_keys=True))
        avg_sensor_reading = json.loads(avg_response.text)
        live_sensor_reading = json.loads(live_response.text)
        pm2_5_reading_avg = (avg_sensor_reading['pm2_5_atm'] + avg_sensor_reading['pm2_5_atm_b']) / 2
        pm2_5_reading_live = (live_sensor_reading['pm2_5_atm'] + live_sensor_reading['pm2_5_atm_b']) / 2
        # Confidence
        avg_confidence = confidence_check(avg_response)
        live_confidence = confidence_check(live_response)
    else:
        logger.error('Error: status code not ok')
        conn_success = False
        pm2_5_reading_avg, pm2_5_reading_live, avg_confidence, live_confidence = 0, 0, 0, 0
    return pm2_5_reading_avg, pm2_5_reading_live, avg_confidence, live_confidence, conn_success


def calc_aqi(PM2_5):
    """
    This function calculates the Air Quality Index (AQI) based on PM2.5 concentration.

    Parameters:
    PM2_5 (float): The PM2.5 concentration in micrograms per cubic meter.

    Returns:
    int: The calculated AQI.
    """
    PM2_5 = max(int(float(PM2_5) * 10) / 10.0, 0)
    #AQI breakpoints (0,    1,     2,    3    )
    #                (Ilow, Ihigh, Clow, Chigh)
    pm25_aqi = (
                [0, 50, 0, 12],
                [51, 100, 12.1, 35.4],
                [101, 150, 35.5, 55.4],
                [151, 200, 55.5, 150.4],
                [201, 300, 150.5, 250.4],
                [301, 500, 250.5, 500.4],
                [301, 500, 250.5, 500.4]
    )
    for values in pm25_aqi:
        Ilow, Ihigh, Clow, Chigh = values
        if Clow <= PM2_5 <= Chigh:
            Ipm25 = int(round(((Ihigh - Ilow) / (Chigh - Clow) * (PM2_5 - Clow) + Ilow)))
            return Ipm25


def exit_handler():
    """
    This function blanks the display anbd exits the program.

    Parameters:
    None

    Returns:
    None
    """
    sleep(.4)
    lcd.color = [0, 0, 0]
    lcd.message = " "
    lcd.clear()
    sleep(.4)
    sys.exit(0)


try:
    display = "on"
    active = True
    avg_reading, live_reading, avg_confidence, live_confidence, conn_success = process_sensor_reading(connection_url)
    if conn_success:
        Ipm25_avg = calc_aqi(avg_reading)
    sleep(1)
    # Loop forever
    while 1:
        if (5 < datetime.datetime.now().hour <= 22) and (active == True):
            avg_reading, live_reading, avg_confidence, live_confidence, conn_success = process_sensor_reading(connection_url)
            if conn_success:
                Ipm25_avg = calc_aqi(avg_reading)
                Ipm25_live = calc_aqi(live_reading)
        elif 22 < datetime.datetime.now().hour < 5:
            active = False
        write_message(Ipm25_avg, Ipm25_live, avg_confidence, live_confidence, conn_success,  display, active)
        delay_loop_start = datetime.datetime.now()
        elapsed_time = datetime.datetime.now() - delay_loop_start
        #Determines refresh interval, add 2 sec to value to get actual refresh interval (+/-)
        while elapsed_time.seconds <= 3:
            elapsed_time = datetime.datetime.now() - delay_loop_start
            write_spinner(conn_success, active)
            if lcd.select_button:
                state_map = {"on": ("off", False), "off": ("on", True)}
                display, active = state_map[display]
                write_message(Ipm25_avg, Ipm25_live, avg_confidence, live_confidence, conn_success, display, active)
            elif lcd.right_button:
                state_map = {True: False, False: True}
                active = state_map[active]
                write_spinner(conn_success, active)
            sleep(.01)

except KeyboardInterrupt:
    exit_handler()