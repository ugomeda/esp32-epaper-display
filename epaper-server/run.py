import io
import time
import json
import logging
import asyncio
import argparse
import click
from aiohttp import web
from epaperengine.display import Display
from epaperengine.asynchronous import display_updater


MINIMUM_WAITING_TIME = 10


class Context:
    def __init__(self):
        self.displays = {}
        self.tokens = {}

    def set_tokens(self, tokens):
        self.tokens = tokens

    def add_display(self, id, display):
        self.displays[id] = display

    def get_status(self, token):
        display_id = self.tokens.get(token)
        if token is None:
            return None

        display = self.displays.get(display_id)
        if display is None:
            return None

        return display.get_status()


routes = web.RouteTableDef()


@routes.get("/get/")
async def serve_image(request):
    status = request.app["context"].get_status(request.headers.get("X-Display-ID"))
    if status is None:
        raise web.HTTPNotFound()

    max_age = max(MINIMUM_WAITING_TIME, round(status["next_update"] - time.monotonic()))
    headers = {"ETag": status["version"], "Cache-Control": f"max-age={max_age}"}

    # Return 304 if content did not change
    client_etag = request.headers.get("ETag")
    if client_etag == status["version"]:
        return web.Response(headers=headers, status=304)

    # Return the image
    output = io.BytesIO()
    status["image"].save(output, format="PNG", bits=2, compress_level=9)
    output.seek(0, 0)
    return web.Response(body=output, content_type="image/png", headers=headers)


async def launch_web_server(context, bind, port):
    app = web.Application()
    app["context"] = context

    runner = web.AppRunner(app)
    app.router.add_routes(routes)

    await runner.setup()
    site = web.TCPSite(runner, bind, port)
    await site.start()
    logging.info(f"Server started at http://{bind}:{port}")

    return runner


async def initialize_displays(context, config_path):
    # Load configuration
    with open(config_path) as config_file:
        config = json.load(config_file)

    context.set_tokens(config["tokens"])

    for id, display_config in config["displays"].items():
        # Add display to the context
        display = Display(display_config)
        context.add_display(id, display)

        # Start the background task to update
        asyncio.create_task(display_updater(id, display))


@click.group(chain=True)
def cli():
    pass


@cli.command()
@click.option("--config", default="config.json", help="The path to the config")
@click.option("--bind", default="127.0.0.1", help="The port to bind to")
@click.option("--port", default=8080, help="The port to listen to")
def run(config, bind, port):
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    loop = asyncio.get_event_loop()

    # Initialize
    context = Context()
    web_server = loop.run_until_complete(launch_web_server(context, bind, port))
    loop.run_until_complete(initialize_displays(context, config))

    # Run until stopped
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")

    # Cleanup servers
    # loop.run_until_complete(image_generator.stop())
    loop.run_until_complete(web_server.cleanup())
    logging.info("Bye bye !")


@cli.command()
@click.option("--config", default="config.json", help="The path to the config")
@click.argument("display")
@click.argument("output")
def gen(config, display, output):
    with open(config) as config_file:
        config = json.load(config_file)

    display = Display(config["displays"][display])
    image = display.update_image()

    image.save(output, format="PNG", compress_level=9)


if __name__ == "__main__":
    cli()
