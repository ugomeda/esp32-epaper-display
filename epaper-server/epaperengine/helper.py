import math
from PIL import Image, ImageFont, ImageDraw, ImageColor


class FontProvider:
    def __init__(self):
        self.cache = {}

    def get(self, name, fontsize):
        # Load from cache
        font = self.cache.get((name, fontsize))
        if font is not None:
            return font

        # Create new font
        font = ImageFont.truetype(
            "epaperengine/resources/fonts/{}".format(name), fontsize
        )
        self.cache[(name, fontsize)] = font

        return font


class ImageProvider:
    def __init__(self):
        self.cache = {}

    def get(self, name):
        image = self.cache.get(name)
        if image is not None:
            return image

        image = Image.open("epaperengine/resources/images/{}".format(name))
        self.cache[name] = image

        return image


class DrawHelper:
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    COLOR = (255, 0, 0)

    def __init__(self, font_provider, image_provider, image):
        self.img = image
        self.draw = ImageDraw.Draw(image)
        self.font_provider = font_provider
        self.image_provider = image_provider

    def font(self, settings):
        return self.font_provider.get(*settings)

    def image(self, name):
        return self.image_provider.get(name)

    def image_centered(self, name, position):
        image = self.image(name)

        x = math.floor(position[0] - image.width / 2)
        y = math.floor(position[1] - image.height / 2)

        self.img.paste(image, (x, y))

    def text_centered(self, text, font, position, **params):
        font_type = self.font(font)
        width, height = self.draw.textsize(text, font_type)
        offset_x, offset_y = font_type.getoffset(text)

        x = math.floor(position[0] - (width + offset_x) / 2)
        y = math.floor(position[1] - (height + offset_y) / 2)

        self.text((x, y), text, font=font, **params)

    def text(self, position, text, font, fill):
        """ Draws a text and returns if width and height.

        The final dithering applied on the image plays badly
        with text.

        The solution is to draw the thex into a temporary monochrome image,
        convert the colors into a transparent image with the correct color
        and paste it into the 
        """
        # Get font and size
        font_type = self.font(font)
        width, height = self.draw.textsize(text, font_type)
        offset_x, offset_y = font_type.getoffset(text)
        fullwidth = width + offset_x
        fullheight = height + offset_y

        # Convert color
        r, g, b = fill

        # Create temporary image and add text
        image = Image.new("1", (fullwidth, fullheight), color=0x000000)
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text, font=font_type, fill=0xFFFFFF)

        # Convert image to transparent and replace colors
        image = image.convert("RGBA")
        pixdata = image.load()
        for y in range(fullheight):
            for x in range(fullwidth):
                # Replace black background with transparent
                if pixdata[x, y] == (0, 0, 0, 255):
                    pixdata[x, y] = (0, 0, 0, 0)
                # Replace white with requested color
                else:
                    pixdata[x, y] = (r, g, b, 255)

        self.img.paste(image, position, image)

        return fullwidth, fullheight
