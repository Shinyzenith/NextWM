# Copyright (c) 2021 Shinyzenith <aakashsensharma@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
import os

from pywayland.server import Display, Listener
from wlroots import helper as wlroots_helper
from wlroots import xwayland
from wlroots.wlr_types import (Cursor, DataControlManagerV1, DataDeviceManager,
                               ExportDmabufManagerV1, GammaControlManagerV1,
                               LayerShellV1)
from wlroots.wlr_types import Output as wlrOutput
from wlroots.wlr_types import (OutputLayout, PrimarySelectionV1DeviceManager,
                               ScreencopyManagerV1, XCursorManager,
                               XdgOutputManagerV1, XdgShell, seat)
from wlroots.wlr_types.idle import Idle
from wlroots.wlr_types.idle_inhibit_v1 import IdleInhibitorManagerV1
from wlroots.wlr_types.input_device import InputDevice, InputDeviceType
from wlroots.wlr_types.output_management_v1 import OutputManagerV1
from wlroots.wlr_types.output_power_management_v1 import OutputPowerManagerV1

from libnext.inputs import NextKeyboard
from libnext.utils import Listeners

log = logging.getLogger("Next: Backend")


class NextCore(Listeners):
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
        log.info(f"WAYLAND_DISPLAY {self.socket.decode()}")

        # Input configuration.
        self.keyboards: list[NextKeyboard] = []

        DataDeviceManager(self.display)
        DataControlManagerV1(self.display)
        self.seat: seat.Seat = seat.Seat(self.display, "NextWM-Seat0")
        self.add_listener(self.backend.new_input_event, self._on_new_input)
        self.add_listener(self.backend.new_output_event, self._on_new_output)

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
        ExportDmabufManagerV1(self.display)
        GammaControlManagerV1(self.display)
        PrimarySelectionV1DeviceManager(self.display)
        ScreencopyManagerV1(self.display)
        XdgOutputManagerV1(self.display, self.output_layout)
        # idle_inhibitor_manager = IdleInhibitorManagerV1(self.display)
        # output_power_manager = OutputPowerManagerV1(self.display)
        _ = IdleInhibitorManagerV1(self.display)
        _ = OutputPowerManagerV1(self.display)
        self.idle = Idle(self.display)

        # XWayland initialization.
        # True -> lazy evaluation.
        # A.K.A XWayland is started when a client needs it.
        self.xwayland = xwayland.XWayland(self.display, self.compositor, True)
        if not self.xwayland:
            log.error("Failed to setup XWayland. Continuing without.")
        else:
            os.environ["DISPLAY"] = self.xwayland.display_name or ""
            log.info(f"XWAYLAND DISPLAY {self.xwayland.display_name}")

        self.backend.start()
        self.backend.get_session().change_vt(2)
        self.display.run()

        # Cleanup
        self.destroy_listeners()
        if self.xwayland:
            self.xwayland.destroy()
        self.cursor.destroy()
        self.output_layout.destroy()
        self.seat.destroy()
        self.backend.destroy()
        self.display.destroy()

    # Properties
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

    # Listeners
    def _on_new_input(self, listener: Listener, device: InputDevice) -> None:
        log.debug("Signal: wlr_backend_new_input_event")
        match device.device_type:
            case InputDeviceType.KEYBOARD:
                self.keyboards.append(NextKeyboard(self, device))
                self.seat.set_keyboard(device)
            case InputDeviceType.POINTER:
                self.cursor.attach_input_device(device)

        # TODO: set the seat capabilities
        log.debug(
            "Device: %s of type %s detected.",
            device.name,
            device.device_type.name.lower(),
        )

    def _on_new_output(self, _: Listener, __: wlrOutput) -> None:
        # TODO: Finish this.
        log.debug("Signal: wlr_backend_new_output_event")
