import math
import requests
import json
import pytz
from dateutil.parser import parse
from datetime import datetime, timedelta
from babel.dates import format_time, get_timezone
from epaperengine.widgets.base import BaseWidget


WEATHER_CODES_TO_IMAGES = {
    "01d": "wi-day-sunny",
    "01n": "wi-moon-new",
    "02d": "wi-day-cloudy",
    "02n": "wi-night-cloudy",
    "03d": "wi-cloud",
    "03n": "wi-cloud",
    "04d": "wi-cloudy",
    "04n": "wi-cloudy",
    "09d": "wi-day-showers",
    "09n": "wi-night-showers",
    "10d": "wi-day-rain",
    "10n": "wi-night-rain",
    "11d": "wi-day-thunderstorm",
    "11n": "wi-night-thunderstorm",
    "13d": "wi-snow",
    "13n": "wi-snow",
    "50d": "wi-fog",
    "50n": "wi-fog",
}

BASE_URL = "https://api.openweathermap.org/data/2.5/"
MIN_WIDTH = 80
HEADER_HEIGHT = 70
NEXT_HEIGHT = 85
SMALL_IMAGE_HEIGHT = 47


class WeatherWidget(BaseWidget):
    fonts = {
        "main_temp": ("OpenSans-Bold-webfont.woff", 35),
        "details": ("OpenSans-Regular-webfont.woff", 22),
        "next": ("OpenSans-Regular-webfont.woff", 18),
        "next_bold": ("OpenSans-Bold-webfont.woff", 18),
    }

    def __init__(self, settings, size):
        # Config
        self.api_key = settings["api_key"]
        self.city_id = settings["city_id"]
        self.units = settings["units"]
        self.lang = settings["locale"].split("_")[0]
        self.timezone = get_timezone(settings["timezone"])
        self.size = size
        self.temperature_format = "{:.0f}°F" if self.units == "imperial" else "{:.0f}°C"

    def _format_wind(self, speed):
        if self.units == "imperial":
            return "{:.0f} mph".format(speed)
        else:
            return "{:.0f} km/h".format(speed * 3.6)

    def update(self):
        # Fetch now
        response = requests.get(
            "{}/weather?id={}&units={}&lang={}&APPID={}".format(
                BASE_URL, self.city_id, self.units, self.lang, self.api_key
            )
        )
        response.raise_for_status()
        self.now = response.json()

        # Fetch forecast
        response = requests.get(
            "{}/forecast?id={}&units={}&lang={}&APPID={}".format(
                BASE_URL, self.city_id, self.units, self.lang, self.api_key
            )
        )
        response.raise_for_status()
        self.forecast = response.json()

    def draw(self, helper):
        # Display
        weather = self.now["weather"][0]
        w, _ = helper.text(
            (95, 6),
            self.temperature_format.format(self.now["main"]["temp"]),
            font=self.fonts["main_temp"],
            fill=helper.BLACK,
        )
        helper.text(
            (100, 50),
            weather["description"],
            font=self.fonts["details"],
            fill=helper.BLACK,
        )
        helper.text(
            (110 + w, 20),
            self._format_wind(self.now["wind"]["speed"]),
            font=self.fonts["details"],
            fill=helper.BLACK,
        )

        # Add icon
        icon = helper.image(
            "weather/{}.png".format(WEATHER_CODES_TO_IMAGES[weather["icon"]])
        )
        helper.img.paste(icon, (0, 5))

        # Display the weather for the rest of the day
        items_count = math.floor(self.size[0] / MIN_WIDTH)
        for i in range(0, items_count):
            x = i * self.size[0] / items_count
            y = HEADER_HEIGHT + (self.size[1] - HEADER_HEIGHT - NEXT_HEIGHT) / 2
            w = self.size[0] / items_count
            h = NEXT_HEIGHT

            weather_data = self.forecast["list"][i]
            weather = weather_data["weather"][0]

            # Date
            date = parse(weather_data["dt_txt"])
            date.replace(tzinfo=pytz.UTC)
            helper.text_centered(
                format_time(
                    date, format="short", locale=self.lang, tzinfo=self.timezone
                ),
                self.fonts["next"],
                (x + w / 2, y + h - 10),
                fill=helper.BLACK,
            )

            # Temperature
            temperature = self.temperature_format.format(
                round(weather_data["main"]["temp"])
            )
            helper.text_centered(
                temperature,
                self.fonts["next_bold"],
                (x + w / 2, y + h - 30),
                fill=helper.BLACK,
            )

            # Icon
            helper.image_centered(
                "weather_small/{}.png".format(WEATHER_CODES_TO_IMAGES[weather["icon"]]),
                (x + w / 2, y + SMALL_IMAGE_HEIGHT / 2),
            )
