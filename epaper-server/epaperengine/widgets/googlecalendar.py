import locale
from pytz import timezone
from dateutil import parser
import os
import pickle
from operator import attrgetter
import json
from babel.dates import format_date, format_time
import requests
from datetime import datetime, date, time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from epaperengine.widgets.base import BaseWidget
from google.auth.transport.requests import Request

EVENT_LINE_HEIGHT = 35
LEFT_MARGIN = 15


class GoogleEvent:
    def __init__(self, event):
        self.title = event["summary"]
        self.start = GoogleEvent.convert_date(event["start"])
        self.end = GoogleEvent.convert_date(event["end"])
        self.created_at = parser.parse(event["created"])

    @staticmethod
    def convert_date(value):
        if "dateTime" in value:
            return parser.parse(value["dateTime"])
        else:
            return date.fromisoformat(value["date"])


class GooglecalendarWidget(BaseWidget):
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, settings, size):
        self.timezone = timezone(settings["timezone"])
        self.locale = settings["locale"]
        self.size = size
        self.credentials = settings["credentials"]
        self.token_store = settings["token_store"]

        # Load creds
        # See https://developers.google.com/calendar/quickstart/python
        self.creds = None
        if os.path.exists(self.token_store):
            with open(self.token_store, "rb") as token:
                self.creds = pickle.load(token)

    def update(self):
        # Authenticate if necessary
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials, self.SCOPES
                )
                self.creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(self.token_store, "wb") as token:
            pickle.dump(self.creds, token)

        # Fetch list of calendars
        service = build("calendar", "v3", credentials=self.creds)

        today = datetime.now(self.timezone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow = datetime.now(self.timezone).replace(
            hour=23, minute=59, second=59, microsecond=0
        )

        calendars = service.calendarList().list().execute()

        calendar_ids = [calendar["id"] for calendar in calendars["items"]]

        # Fetch events
        all_events = []
        for calendar_id in calendar_ids:
            events = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    orderBy="startTime",
                    singleEvents=True,
                    timeMin=today.isoformat(),
                    timeMax=tomorrow.isoformat(),
                )
                .execute()
            )

            for event in events["items"]:
                all_events.append(GoogleEvent(event))

        # Sort events
        all_events.sort(key=attrgetter("created_at"))

        day_events = list(
            filter(lambda event: not isinstance(event.start, datetime), all_events)
        )
        hour_events = list(
            filter(lambda event: isinstance(event.start, datetime), all_events)
        )

        day_events.sort(key=attrgetter("start"))
        hour_events.sort(key=attrgetter("start"))

        self.events = day_events + hour_events

    def draw(self, helper):
        # Add background
        helper.draw.rectangle(
            xy=[(0, 0), (self.size[0], self.size[1])], fill=helper.BLACK,
        )

        # Add date
        now = datetime.now(self.timezone)
        text = format_date(now, format="medium", locale=self.locale)
        helper.text(
            (LEFT_MARGIN, 32),
            text,
            font=("OpenSans-Bold-webfont.woff", 40),
            fill=helper.COLOR,
        )

        text = format_date(now, format="EEEE", locale=self.locale)
        helper.text(
            (LEFT_MARGIN, 10),
            text,
            font=("OpenSans-Regular-webfont.woff", 25),
            fill=helper.COLOR,
        )

        # Add day events
        event_count = 0
        for event in self.events:
            top = 110 + event_count * EVENT_LINE_HEIGHT

            if isinstance(event.start, datetime):
                time_label = format_time(
                    event.start, format="HH:mm", locale=self.locale
                )
            else:
                # Remove date in the most hacky way
                time_label = format_date(
                    event.start, format="dd/MM", locale=self.locale
                )

            helper.text(
                (LEFT_MARGIN, top - 1),
                time_label,
                font=("OpenSans-Bold.ttf", 18),
                fill=helper.WHITE,
            )

            helper.text(
                (LEFT_MARGIN + 60, top),
                event.title,
                font=("OpenSans-Regular-webfont.woff", 18),
                fill=helper.WHITE,
            )
            helper.draw.line(
                ((LEFT_MARGIN, top + 28), (self.size[0], top + 28)),
                fill=helper.COLOR,
                width=0,
            )

            event_count += 1
