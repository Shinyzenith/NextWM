# Copyright (c) 2022 Shinyzenith <aakashsensharma@gmail.com>
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
import signal
from typing import cast

from pywayland.protocol.wayland import WlSeat
from pywayland.server import Display, Listener
from wlroots import helper as wlroots_helper
from wlroots import xwayland
from wlroots.wlr_types import (
    Cursor,
    DataControlManagerV1,
    DataDeviceManager,
    ExportDmabufManagerV1,
    ForeignToplevelManagerV1,
    GammaControlManagerV1,
    Output,
    OutputLayout,
    PrimarySelectionV1DeviceManager,
    Scene,
    SceneNode,
    ScreencopyManagerV1,
    Surface,
    XCursorManager,
    XdgOutputManagerV1,
    seat,
)
from wlroots.wlr_types.idle import Idle
from wlroots.wlr_types.idle_inhibit_v1 import IdleInhibitorManagerV1
from wlroots.wlr_types.input_device import InputDevice, InputDeviceType
from wlroots.wlr_types.layer_shell_v1 import LayerShellV1, LayerSurfaceV1
from wlroots.wlr_types.output_management_v1 import OutputManagerV1
from wlroots.wlr_types.output_power_management_v1 import OutputPowerManagerV1
from wlroots.wlr_types.xdg_shell import XdgShell, XdgSurface, XdgSurfaceRole

from libnext.inputs import NextKeyboard
from libnext.outputs import NextOutput
from libnext.util import Listeners
from libnext.window import WindowType, XdgWindow

log = logging.getLogger("Next: Backend")


class NextCore(Listeners):
    def __init__(self) -> None:
        """
        Setup nextwm
        """
        self.display: Display = Display()
        self.event_loop = self.display.get_event_loop()

        for handled_signal in [
            signal.SIGINT,
            signal.SIGTERM,
            signal.SIGABRT,
            signal.SIGKILL,
            signal.SIGQUIT,
        ]:
            self.event_loop.add_signal(
                handled_signal, self.signal_callback, self.display
            )

        (
            self.compositor,
            self.allocator,
            self.renderer,
            self.backend,
        ) = wlroots_helper.build_compositor(self.display)
        self.renderer.init_display(self.display)
        self.socket = self.display.add_socket()
        os.environ["WAYLAND_DISPLAY"] = self.socket.decode()
        log.info(f"WAYLAND_DISPLAY {self.socket.decode()}")

        # These windows have not been mapped yet.
        # They'll get managed when mapped.
        self.pending_windows: set[WindowType] = set()
        self.mapped_windows: list[WindowType] = []

        # List of outputs managed by the compositor.
        self.outputs: list[NextOutput] = []

        # Input configuration.
        self.keyboards: list[NextKeyboard] = []

        DataDeviceManager(self.display)
        DataControlManagerV1(self.display)
        self.seat: seat.Seat = seat.Seat(self.display, "NextWM-Seat0")
        self.add_listener(self.backend.new_input_event, self._on_new_input)
        self.add_listener(self.backend.new_output_event, self._on_new_output)

        # Output configuration.
        self.output_layout: OutputLayout = OutputLayout()
        self.scene: Scene = Scene(self.output_layout)
        self.output_manager: OutputManagerV1 = OutputManagerV1(self.display)

        # Cursor configuration
        self.cursor: Cursor = Cursor(self.output_layout)
        self.cursor_manager: XCursorManager = XCursorManager(24)

        # Setup Xdg shell
        self.xdg_shell: XdgShell = XdgShell(self.display)
        self.add_listener(self.xdg_shell.new_surface_event, self._on_new_xdg_surface)
        self.layer_shell: LayerShellV1 = LayerShellV1(self.display)
        self.add_listener(
            self.layer_shell.new_surface_event, self._on_new_layer_surface
        )

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
        self.foreign_toplevel_managerv1 = ForeignToplevelManagerV1.create(self.display)

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
        self.display.run()

        # Cleanup
        self.destroy()

    def signal_callback(self, sig_num: int, display: Display):
        log.info("Terminating event loop.")
        display.terminate()

    # Resource cleanup.
    def destroy(self) -> None:
        self.destroy_listeners()

        for keyboard in self.keyboards:
            keyboard.destroy_listeners()

        for output in self.outputs:
            output.destroy_listeners()

        if self.xwayland:
            self.xwayland.destroy()
        self.cursor.destroy()
        self.output_layout.destroy()
        self.seat.destroy()
        self.backend.destroy()
        self.display.destroy()

    def focus_window(self, window: WindowType, surface: Surface | None = None) -> None:
        if self.seat.destroyed:
            return
        if surface is None and window is not None:
            surface = window.surface.surface

        previous_surface = self.seat.keyboard_state.focused_surface
        if previous_surface == surface:
            log.info("Focus requested on currently focused surface. Focus unchanged.")
            return

        if previous_surface is not None:
            if previous_surface.is_xdg_surface:
                previous_xdg_surface = XdgSurface.from_surface(previous_surface)
                if not window or window.surface != previous_xdg_surface:
                    previous_xdg_surface.set_activated(False)
                    if previous_xdg_surface.data:  # We store the ftm handle in data.
                        previous_xdg_surface.data.set_activated(False)

            if previous_surface.is_xwayland_surface:
                previous_xwayland_surface = xwayland.Surface.from_wlr_surface(
                    previous_surface
                )
                if not window or window.surface != previous_xwayland_surface:
                    previous_xwayland_surface.activate(False)
                    if (
                        previous_xwayland_surface.data
                    ):  # We store the ftm handle in data.
                        previous_xwayland_surface.data.set_activated(False)

        if not window:
            self.seat.keyboard_clear_focus()
            return

        log.info("Focusing on surface.")
        window.scene_node.raise_to_top()

        # Preventing race conditions.
        windows = self.mapped_windows[:]
        windows.remove(window)
        windows.append(window)
        self.mapped_windows = windows

        window.surface.set_activated(True)
        if window.surface.data:
            window.surface.set_activated(True)  # Setting ftm_handle to activated_true

        self.seat.keyboard_notify_enter(window.surface.surface, self.seat.keyboard)

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
    def _on_new_input(self, _: Listener, device: InputDevice) -> None:
        log.info("Signal: wlr_backend_new_input_event")
        match device.device_type:
            case InputDeviceType.KEYBOARD:
                self.keyboards.append(NextKeyboard(self, device))
                self.seat.set_keyboard(device)
            case InputDeviceType.POINTER:
                self.cursor.attach_input_device(device)

        # Fetching capabilities
        capabilities = WlSeat.capability.pointer
        if self.keyboards:
            capabilities |= WlSeat.capability.keyboard

        self.seat.set_capabilities(capabilities)
        # TODO:Set libinput settings as needed after setting capabilities

        log.info(
            "Device: %s of type %s detected.",
            device.name,
            device.device_type.name.lower(),
        )

    def _on_new_output(self, _: Listener, wlr_output: Output) -> None:
        log.info("Signal: wlr_backend_new_output_event")

        wlr_output.init_render(self.allocator, self.renderer)

        if wlr_output.modes != []:
            mode = wlr_output.preferred_mode()
            if mode is None:
                log.error("New output advertised with no output mode")
            wlr_output.set_mode(mode)
            wlr_output.enable()
            wlr_output.commit()

        NextOutput(self, wlr_output)

    def _on_new_xdg_surface(self, _: Listener, surface: XdgSurface) -> None:
        log.info("Signal: xdg_shell_new_xdg_surface_event")
        match surface.role:
            case XdgSurfaceRole.TOPLEVEL:
                self.pending_windows.add(XdgWindow(self, surface))

            case XdgSurfaceRole.POPUP:
                parent_surface = XdgSurface.from_surface(surface.popup.parent)
                parent_scene_node = cast(SceneNode, parent_surface.data)

                scene_node = SceneNode.xdg_surface_create(parent_scene_node, surface)
                surface.data = scene_node

    def _on_new_layer_surface(self, _: Listener, surface: LayerSurfaceV1) -> None:
        log.info("Signal layer_shell_new_layer_surface_event")
