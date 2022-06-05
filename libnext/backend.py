import os

from pywayland.server import Display
from wlroots import helper as wlroots_helper
from wlroots import xwayland
from wlroots.wlr_types import (Cursor, DataControlManagerV1, DataDeviceManager,
                               GammaControlManagerV1, LayerShellV1,
                               OutputLayout, PrimarySelectionV1DeviceManager,
                               ScreencopyManagerV1, XCursorManager,
                               XdgOutputManagerV1, XdgShell, seat)
from wlroots.wlr_types.idle import Idle
from wlroots.wlr_types.idle_inhibit_v1 import IdleInhibitorManagerV1
from wlroots.wlr_types.output_management_v1 import OutputManagerV1
from wlroots.wlr_types.output_power_management_v1 import OutputPowerManagerV1


class Core():
    def __init__(self) -> None:
        """
        Setup nextwm
        """
        self.display: Display = Display()
        self.event_loop = self.display.get_event_loop()
        (
            self.compositor,
            self.allocator,
            self.renderer,
            self.backend
        ) = wlroots_helper.build_compositor(self.display)
        self.renderer.init_display(self.display)
        self.socket = self.display.add_socket()
        os.environ["WAYLAND_DISPLAY"] = self.socket.decode()
        print("Starting NextWM on WAYLAND_DISPLAY", self.socket.decode())

        # Input configuration.
        DataDeviceManager(self.display)
        DataControlManagerV1(self.display)
        self.seat: seat.Seat = seat.Seat(self.display, "NextWM-Seat0")

        # Output configuration.
        self.output_layout: OutputLayout = OutputLayout()
        self.output_manager: OutputManagerV1 = OutputManagerV1(self.display)

        # Cursor configuration
        self.cursor: Cursor = Cursor(self.output_layout)
        self.cursor_manager: XCursorManager = XCursorManager(24)

        # Setup Xdg shell
        self.xdg_shell: XdgShell = XdgShell(self.display)
        self.layer_shell: LayerShellV1 = LayerShellV1(self.display)

        # Some protocol initialization.
        XdgOutputManagerV1(self.display, self.output_layout)
        ScreencopyManagerV1(self.display)
        GammaControlManagerV1(self.display)
        # output_power_manager = OutputPowerManagerV1(self.display)
        _ = OutputPowerManagerV1(self.display)
        self.idle = Idle(self.display)
        # idle_inhibitor_manager = IdleInhibitorManagerV1(self.display)
        _ = IdleInhibitorManagerV1(self.display)
        PrimarySelectionV1DeviceManager(self.display)

        # XWayland initialization.
        # True -> lazy evaluation.
        # A.K.A XWayland is started when a client needs it.
        self.xwayland = xwayland.XWayland(self.display, self.compositor, True)
        if not self.xwayland:
            print("Failed to setup XWayland. Continuing without.")
        else:
            os.environ["DISPLAY"] = self.xwayland.display_name or ""
            print("Starting XWayland on", self.xwayland.display_name)

        self.backend.start()
        self.display.run()

        # Cleanup
        if self.xwayland:
            self.xwayland.destroy()
        self.cursor.destroy()
        self.output_layout.destroy()
        self.seat.destroy()
        self.backend.destroy()
        self.display.destroy()

    @property
    def wayland_socket_name(self) -> str:
        """
        The socket name.
        You can access it at /run/user/$(InvokingUserId)/$(socket_name)
        """
        return self.socket.decode()

    @property
    def xwayland_socket_name(self) -> str:
        """
        XWayland socket name.
        """
        return self.xwayland.display_name or ""
