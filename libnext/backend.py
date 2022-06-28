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
from typing import Any

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
    ScreencopyManagerV1,
    Surface,
    XCursorManager,
    XdgOutputManagerV1,
    seat,
    xdg_decoration_v1,
)
from wlroots.wlr_types.cursor import WarpMode
from wlroots.wlr_types.idle import Idle
from wlroots.wlr_types.idle_inhibit_v1 import IdleInhibitorManagerV1
from wlroots.wlr_types.input_device import InputDevice, InputDeviceType
from wlroots.wlr_types.layer_shell_v1 import LayerShellV1, LayerSurfaceV1
from wlroots.wlr_types.output_management_v1 import OutputManagerV1
from wlroots.wlr_types.output_power_management_v1 import OutputPowerManagerV1
from wlroots.wlr_types.pointer import (
    PointerEventAxis,
    PointerEventButton,
    PointerEventMotion,
    PointerEventMotionAbsolute,
)
from wlroots.wlr_types.xdg_shell import XdgShell, XdgSurface, XdgSurfaceRole

from libnext.inputs import NextKeyboard
from libnext.layout_manager import LayoutManager
from libnext.outputs import NextOutput
from libnext.util import Listeners
from libnext.window import WindowType, XdgWindow

log = logging.getLogger("Next: Backend")


class NextCore(Listeners):
    def __init__(self) -> None:
        """
        Setup nextwm
        """
        if os.getenv("XDG_RUNTIME_DIR") is None or os.getenv("XDG_RUNTIME_DIR") == "":
            log.error("XDG_RUNTIME_DIR is not set in the environment")
            return

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

        self.add_listener(self.backend.new_input_event, self._on_new_input)
        self.add_listener(self.backend.new_output_event, self._on_new_output)

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
        self.add_listener(
            self.seat.request_set_selection_event, self._on_request_set_selection
        )
        self.add_listener(
            self.seat.request_set_primary_selection_event,
            self._on_request_set_primary_selection,
        )
        self.add_listener(
            self.seat.request_set_cursor_event, self._on_request_set_cursor
        )
        # TODO: Bind more seat listeners

        # Output configuration.
        self.output_layout: OutputLayout = OutputLayout()
        self.scene: Scene = Scene(self.output_layout)
        self.output_manager: OutputManagerV1 = OutputManagerV1(self.display)
        self.layout_manager = LayoutManager(self.display)

        # Cursor configuration
        self.cursor: Cursor = Cursor(self.output_layout)
        self.cursor_manager: XCursorManager = XCursorManager(24)
        self.add_listener(self.cursor.axis_event, self._on_cursor_axis)
        self.add_listener(self.cursor.button_event, self._on_cursor_button)
        self.add_listener(self.cursor.frame_event, self._on_cursor_frame)
        # TODO: On motion check the view under the cursor and focus.
        # Or focus on click?
        self.add_listener(self.cursor.motion_event, self._on_cursor_motion)
        self.add_listener(
            self.cursor.motion_absolute_event, self._on_cursor_motion_absolute
        )

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

        self.xdg_decoration_manager_v1 = (
            xdg_decoration_v1.XdgDecorationManagerV1.create(self.display)
        )
        self.add_listener(
            self.xdg_decoration_manager_v1.new_toplevel_decoration_event,
            self._on_new_toplevel_decoration,
        )

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
        log.info("Terminating event loop")
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
        self.layout_manager.destroy()
        self.cursor.destroy()
        self.cursor_manager.destroy()
        self.output_layout.destroy()
        self.seat.destroy()
        self.backend.destroy()
        self.display.destroy()
        log.debug("Server destroyed")

    def focus_window(self, window: WindowType, surface: Surface | None = None) -> None:
        if self.seat.destroyed:
            return
        if surface is None and window is not None:
            surface = window.surface.surface

        previous_surface = self.seat.keyboard_state.focused_surface
        if previous_surface == surface:
            log.error("Focus requested on currently focused surface. Focus unchanged.")
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

        log.debug("Focusing on surface")
        window.scene_node.raise_to_top()
        window.surface.set_activated(True)
        if window.surface.data:
            window.surface.set_activated(True)  # Setting ftm_handle to activated_true

        self.seat.keyboard_notify_enter(window.surface.surface, self.seat.keyboard)

    def hide_cursor(self) -> None:
        log.debug("Hiding cursor")
        # TODO: Finish this.
        # XXX:lib.wlr_cursor_set_image(self.cursor._ptr, None, 0, 0, 0, 0, 0, 0)
        # XXX:self.cursor.set_cursor_image(None, 0, 0, 0, 0, 0, 0)
        log.debug("Clearing pointer focus")
        self.seat.pointer_notify_clear_focus()

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
    def _on_new_input(self, _listener: Listener, device: InputDevice) -> None:
        log.debug("Signal: wlr_backend_new_input_event")
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
        # TODO: Set libinput settings as needed after setting capabilities

        log.debug(
            "Device: %s of type %s detected.",
            device.name,
            device.device_type.name.lower(),
        )

    def _on_new_output(self, _listener: Listener, wlr_output: Output) -> None:
        log.debug("Signal: wlr_backend_new_output_event")

        wlr_output.init_render(self.allocator, self.renderer)

        if wlr_output.modes != []:
            mode = wlr_output.preferred_mode()
            if mode is None:
                log.error("New output advertised with no output mode")
            else:
                wlr_output.set_mode(mode)
                wlr_output.enable()
                wlr_output.commit()

        NextOutput(self, wlr_output)

    def _on_request_set_selection(
        self, _listener: Listener, event: seat.RequestSetSelectionEvent
    ) -> None:
        log.debug("Signal: wlr_seat_request_set_selection_event")
        self.seat.set_selection(event._ptr.source, event.serial)

    def _on_request_set_primary_selection(
        self, _listener: Listener, event: seat.RequestSetPrimarySelectionEvent
    ) -> None:
        log.debug("Signal: wlr_seat_on_request_set_primary_selection_event")
        self.seat.set_primary_selection(event._ptr.source, event.serial)

    def _on_request_set_cursor(
        self, _listener: Listener, event: seat.PointerRequestSetCursorEvent
    ) -> None:
        log.debug("Signal: wlr_seat_on_request_set_cursor")
        self.cursor.set_surface(event.surface, event.hotspot)

    def _on_cursor_frame(self, _listener: Listener, data: Any) -> None:
        log.debug("Signal: wlr_cursor_frame_event")
        self.seat.pointer_notify_frame()

    def _on_cursor_motion(
        self, _listener: Listener, event_motion: PointerEventMotion
    ) -> None:
        # TODO: This should get abstracted into it's own function to check if
        # image shoud be ptr or resize type.
        # TODO: Finish this.
        log.debug("Signal: wlr_cursor_motion_event")
        self.cursor.move(
            event_motion.delta_x, event_motion.delta_y, input_device=event_motion.device
        )
        self.cursor_manager.set_cursor_image("left_ptr", self.cursor)

    def _on_cursor_motion_absolute(
        self, _listener: Listener, event_motion: PointerEventMotionAbsolute
    ) -> None:
        log.debug("Signal: wlr_cursor_motion_absolute_event")
        self.cursor.warp(
            WarpMode.LayoutClosest,
            event_motion.x,
            event_motion.y,
            input_device=event_motion.device,
        )
        # TODO: Finish this.

    def _on_cursor_axis(self, _listener: Listener, event: PointerEventAxis) -> None:
        self.seat.pointer_notify_axis(
            event.time_msec,
            event.orientation,
            event.delta,
            event.delta_discrete,
            event.source,
        )

    def _on_cursor_button(self, _listener: Listener, event: PointerEventButton) -> None:
        log.debug("Signal: wlr_cursor_button_event")
        self.idle.notify_activity(self.seat)
        # TODO: If config wants focus_by_hover then do so, else focus_by_click.

        # NOTE: Maybe support compositor bindings involving buttons?
        self.seat.pointer_notify_button(
            event.time_msec, event.button, event.button_state
        )
        log.debug("Cursor button emitted to focused client")

    def _on_new_xdg_surface(self, _listener: Listener, surface: XdgSurface) -> None:
        log.debug("Signal: xdg_shell_new_xdg_surface_event")
        if surface.role == XdgSurfaceRole.TOPLEVEL:
            self.pending_windows.add(XdgWindow(self, surface))

    def _on_new_layer_surface(
        self, _listener: Listener, surface: LayerSurfaceV1
    ) -> None:
        log.debug("Signal: layer_shell_new_layer_surface_event")

    def _on_new_toplevel_decoration(
        self, _listener: Listener, decoration: xdg_decoration_v1.XdgToplevelDecorationV1
    ) -> None:
        log.debug("Signal: xdg_decoration_v1_new_toplevel_decoration_event")
        # TODO: https://github.com/Shinyzenith/NextWM/issues/10
        decoration.set_mode(xdg_decoration_v1.XdgToplevelDecorationV1Mode.SERVER_SIDE)
