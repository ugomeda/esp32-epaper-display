import logging
from PIL import Image, ImageChops, ImagePalette
from datetime import timedelta
from epaperengine import widgets
from epaperengine.utils import parse_dimensions, parse_position
from epaperengine.helper import DrawHelper, FontProvider, ImageProvider

logger = logging.getLogger(__name__)


class Display:
    def __init__(self, config):
        dimensions = parse_dimensions(config["size"])
        self.width = dimensions[0]
        self.height = dimensions[1]
        self.widgets = []
        self.update_interval = timedelta(seconds=config["updateEvery"])
        self.status = None
        self.rotate = config.get("rotate", 0)

        # Create widgets
        settings = config["settings"]
        for widget in config["widgets"]:
            size = parse_dimensions(widget["size"])
            widget_class = getattr(widgets, widget["widget"].capitalize() + "Widget")
            widget_settings = widget.get("settings", {})

            widget_obj = widget_class({**settings, **widget_settings}, size)

            self.widgets.append((widget_obj, parse_position(widget["position"]), size))

        # Initialize caches
        self.font_provider = FontProvider()
        self.image_provider = ImageProvider()

    def update_image(self):
        logger.info("Updating widgets...")
        for widget, _, _ in self.widgets:
            widget.update()

        logger.info("Create image...")
        image = Image.new(mode="RGB", size=(self.width, self.height), color=0xFFFFFF)

        for widget, position, size in self.widgets:
            # Create image
            widget_image = Image.new(mode="RGB", size=size, color=0xFFFFFF)
            helper = DrawHelper(self.font_provider, self.image_provider, widget_image)
            widget.draw(helper)

            # Paste image into the main image
            image.paste(widget_image, position)

        # Convert image with the right palette
        pal_img = Image.new("P", (1, 1))
        pal_img.putpalette([0, 0, 0, 255, 255, 255, 255, 0, 0, 0, 0, 0] * 64)

        return image.rotate(self.rotate, expand=True).quantize(palette=pal_img)

        # return image.quantize(colors=3, palette=[0, 0, 0, 255, 255, 255, 255, 0, 0])

    def set_status(self, status):
        self.status = status

    def get_status(self):
        return self.status
