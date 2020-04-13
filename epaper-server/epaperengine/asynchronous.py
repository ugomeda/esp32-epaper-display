import time
import logging
import asyncio
from PIL import ImageChops
from epaperengine.utils import random_string

logger = logging.getLogger(__name__)

# Ask the display to request the image 20 seconds after the update time to
# give time to the widgets to update and re-render
TIME_MARGIN = 20


def images_equal(image_1, image_2):
    # Initialization
    if image_1 is None:
        return True

    return ImageChops.difference(image_1, image_2).getbbox() is not None


async def display_updater(id, display):
    current_image = None
    image_version = None

    while True:
        try:
            # Load new image
            logger.info(f"Updating display {id}")
            loop = asyncio.get_running_loop()
            new_image = await loop.run_in_executor(None, display.update_image)
            logger.info(f"Loaded image for display {id}")

            is_different = await loop.run_in_executor(
                None, images_equal, current_image, new_image
            )

            if is_different:
                image_version = random_string(32)
                current_image = new_image
                logger.info(f"Display {id} updated to version {image_version}")

            # Update current image
            display.set_status(
                {
                    "version": image_version,
                    "image": current_image,
                    "next_update": time.monotonic()
                    + display.update_interval.total_seconds()
                    + TIME_MARGIN,
                }
            )
            await asyncio.sleep(display.update_interval.total_seconds())
        except KeyboardInterrupt:
            raise
        except:
            logger.exception(
                f"Error while updating display {id}, retrying in 60 seconds"
            )
            await asyncio.sleep(60)
