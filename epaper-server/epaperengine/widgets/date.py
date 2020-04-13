import locale
from pytz import timezone
from babel.dates import format_date
from datetime import datetime
from epaperengine.widgets.base import BaseWidget


class DateWidget(BaseWidget):
    def __init__(self, settings, size):
        self.timezone = timezone(settings["timezone"])
        self.locale = settings["locale"]
        self.size = size

    def draw(self, helper):
        # Add background
        helper.draw.rectangle(
            xy=[(0, 0), (self.size[0], self.size[1])], fill=helper.BLACK,
        )

        # Add left clock
        now = datetime.now(self.timezone)

        # Add right date
        text = format_date(now, format="full", locale=self.locale)
        w, h = helper.draw.textsize(
            text, helper.font(("OpenSans-Bold-webfont.woff", self.size[1] - 41))
        )
        helper.text(
            (self.size[0] - 20 - w, round((self.size[1] - h) / 2)),
            text,
            font=("OpenSans-Bold-webfont.woff", self.size[1] - 41),
            fill=helper.WHITE,
        )
