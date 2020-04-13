import random
import string


def parse_dimensions(dimensions):
    # FIXME Error handling
    return list(map(int, dimensions.split("x")))


def parse_position(position):
    # FIXME Error handling
    return list(map(int, position.split(", ")))


def random_string(length):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))
