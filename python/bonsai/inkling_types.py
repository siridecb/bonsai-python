
from struct import pack


def Float32(func):
    """Float32 tells the system, the reward function returns a the float32
    inkling type.
    TODO: add parameters to specify the range and precision of this type.
    """
    def helper(*args, **kwargs):
        return func(*args, **kwargs)
    helper.__name__ = func.__name__

    return helper


class Luminance(object):
    """This class represents the inkling built in Luminance type."""

    def __init__(self, width, height, pixels):
        if type(pixels) is bytes:
            if len(pixels) != width * height * 4:
                raise ValueError(
                    "Argument pixels has length {}, should be of length "
                    "{}".format(len(pixels), width * height * 4))
            self.pixels = pixels
        else:
            try:  # Assume iterable
                if len(pixels) != width * height:
                    raise ValueError(
                        "Argument pixels has length {}, should be of length "
                        "{}".format(len(pixels), width * height))
                self.pixels = pack('%sf' % len(pixels), *pixels)
            except TypeError:  # Catch failure
                raise TypeError(
                    "Argument pixels has type {}, should be type "
                    "bytes or iterable".format(type(pixels)))

        self.width = width
        self.height = height

    @classmethod
    def from_pil_luminance_image(cls, image):
        """Constructs a Luminance class from the input PIL image. The
        input PIL image must have mode 'L'.
        """
        if image.mode != "L":
            raise ValueError("Argument image must have mode 'L'")
        pixels = [x / 255 for x in image.tobytes()]
        return cls(image.size[0], image.size[1], pixels)
