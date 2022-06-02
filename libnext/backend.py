import os
import signal
from functools import partial

from pywayland.server import Display
from wlroots import helper as wlroots_helper


class Core():
    def __init__(self) -> None:
        """Setup the Wayland core backend"""
        self.display = Display()
        self.event_loop = self.display.get_event_loop()
        (
            self.compositor,
            self.allocator,
            self.renderer,
            self.backend
        ) = wlroots_helper.build_compositor(self.display)
        self.socket = self.display.add_socket()
        os.environ["WAYLAND_DISPLAY"] = self.socket.decode()
        print("Starting NextWM on WAYLAND_DISPLAY=%s", self.socket.decode())

        self.backend.start()
        self.display.run()

        self.backend.destroy()
        self.display.destroy()

    @property
    def display_name(self) -> str:
        return self.socket.decode()
