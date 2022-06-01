import signal
from functools import partial

from pywayland.server import Display
from wlroots.allocator import Allocator
from wlroots.backend import Backend, BackendType
from wlroots.renderer import Renderer
from wlroots.wlr_types import Compositor


def callback(display: Display, signal_num, stack_frame) -> None:
    del signal_num, stack_frame # We don't need these at the moment.
    print("Terminating NextWM")
    display.terminate()

def init() -> None:
    with Display() as display:
        signal.signal(signal.SIGINT, partial(callback, display))

        backend = Backend(display, backend_type=BackendType.AUTO)
        renderer = Renderer.autocreate(backend)
        renderer.init_display(display)
        allocator = Allocator.autocreate(backend, renderer)
        compositor = Compositor(display, renderer)

        socket = display.add_socket()
        print("socket: ", socket.decode())
        with backend:
            display.run()

        del allocator # Don't need this at the moment.
        del compositor # Don't need this at the moment.
