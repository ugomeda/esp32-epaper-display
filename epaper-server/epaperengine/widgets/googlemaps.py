import io
import math
import logging
import googlemaps
from babel.dates import format_timedelta
from datetime import datetime, timedelta
from PIL import Image
from epaperengine.widgets.base import BaseWidget

logger = logging.getLogger(__name__)

HEADER_SIZE = 70


class GooglemapsWidget(BaseWidget):
    fonts = {
        "route": ("OpenSans-Regular-webfont.woff", 18),
        "time": ("OpenSans-Bold-webfont.woff", 28),
    }

    def __init__(self, settings, size):
        self.key = settings["client_key"]
        self.home = settings["home_address"]
        self.work = settings["work_address"]
        self.units = settings["units"]
        self.locale = settings["locale"]
        self.size = size

        # State
        self.client = googlemaps.Client(key=self.key)
        self.map_cache = {}
        self.map = None
        self.directions = None

    def _fetch_map(self, directions):
        path = directions[0]["overview_polyline"]["points"]

        if path in self.map_cache:
            return self.map_cache[path]

        logger.info("Fetching map not in cache")

        width = self.size[0]
        height = self.size[1] - HEADER_SIZE

        arguments = {
            "size": f"{width}x{height}",
            "path": (
                "color:0x000000FF|weight:6|enc:"
                + directions[0]["overview_polyline"]["points"]
            ),
            "style": "visibility:simplified",
        }

        response = self.client._request(
            url="/maps/api/staticmap", params=arguments, extract_body=lambda r: r
        )
        response.raise_for_status()

        if "X-Staticmap-API-Warning" in response.headers:
            logger.warn(response.headers["X-Staticmap-API-Warning"])

        # Save to cache and return
        self.map_cache[path] = response.content

        return self.map_cache[path]

    def update(self):
        now = datetime.now()

        # Fetch directions
        directions = self.client.directions(
            self.home, self.work, units=self.units, mode="driving", departure_time=now
        )

        # Load map
        map = self._fetch_map(directions)

        # Save if everything went right
        self.map = map
        self.directions = directions

    def draw(self, helper):
        time = timedelta(
            seconds=self.directions[0]["legs"][0]["duration_in_traffic"]["value"]
        )
        route = self.directions[0]["summary"]

        # Display the time
        helper.text(
            (20, self.size[1] - HEADER_SIZE + 3),
            format_timedelta(time, locale=self.locale),
            font=self.fonts["time"],
            fill=helper.BLACK,
        )

        # Display the route
        helper.text(
            (20, self.size[1] - HEADER_SIZE + 37),
            route,
            font=self.fonts["route"],
            fill=helper.BLACK,
        )

        # Display the image
        helper.img.paste(Image.open(io.BytesIO(self.map)).convert("RGB"), (0, 0))
