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
import subprocess
from typing import Any

from pywayland.protocol.wayland import WlKeyboard
from pywayland.server import Listener
from wlroots import ffi, lib, xwayland
from wlroots.wlr_types import InputDevice
from wlroots.wlr_types.keyboard import KeyboardKeyEvent, KeyboardModifier
from wlroots.wlr_types.xdg_shell import XdgSurface
from xkbcommon import xkb

from libnext.util import Listeners

log = logging.getLogger("Next: Inputs")
xkb_keysym = ffi.new("const xkb_keysym_t **")


class NextKeyboard(Listeners):
    def __init__(self, core, device: InputDevice):
        self.device = device
        self.keyboard = device.keyboard
        self.core = core

        # NOTE: https://github.com/Shinyzenith/NextWM/issues/5
        self.keyboard.set_repeat_info(100, 300)
        self.xkb_context = xkb.Context()

        # TODO: Populate this keymap call later.
        self.keymap = self.xkb_context.keymap_new_from_names()
        self.keyboard.set_keymap(self.keymap)

        self.add_listener(self.keyboard.destroy_event, self._on_destroy)
        self.add_listener(self.keyboard.key_event, self._on_key)
        self.add_listener(self.keyboard.modifiers_event, self._on_modifiers)

    def destroy(self) -> None:
        self.destroy_listeners()
        self.core.keyboards.remove(self)
        if self.core.keyboards and self.core.seat.keyboard.destroyed:
            self.core.seat.set_keyboard(self.core.keyboards[-1].device)

    # Listeners
    def _on_destroy(self, _listener: Listener, _data: Any) -> None:
        log.debug("Signal: wlr_keyboard_destroy_event")
        self.destroy()

    def _on_key(self, _listener: Listener, key_event: KeyboardKeyEvent) -> None:
        log.debug("Signal: wlr_keyboard_key_event")
        # TODO: Add option to hide cursor when typing.
        # self.core.cursor.hide() -> From river.

        # Translate libinput keycode -> xkbcommon
        keycode = key_event.keycode + 8

        layout_index = lib.xkb_state_key_get_layout(
            self.keyboard._ptr.xkb_state, keycode
        )
        nsyms = lib.xkb_keymap_key_get_syms_by_level(
            self.keyboard._ptr.keymap, keycode, layout_index, 0, xkb_keysym
        )
        keysyms = [xkb_keysym[0][i] for i in range(nsyms)]
        for keysym in keysyms:
            # TODO: Support change_vt()
            if (
                self.keyboard.modifier == KeyboardModifier.ALT
                and key_event.state == WlKeyboard.key_state.pressed  # noqa: W503
            ):
                if keysym == xkb.keysym_from_name("Escape"):
                    # We don't care for sig_num anyways.
                    self.core.signal_callback(0, self.core.display)
                    return

                if keysym == xkb.keysym_from_name("l"):
                    subprocess.Popen(["alacritty"])
                    return

                if keysym == xkb.keysym_from_name("j"):
                    if len(self.core.mapped_windows) >= 2:
                        window = self.core.mapped_windows.pop()
                        self.core.mapped_windows.insert(0, window)
                        self.core.focus_window(self.core.mapped_windows[-1])
                        return

                if keysym == xkb.keysym_from_name("k"):
                    if len(self.core.mapped_windows) >= 2:
                        window = self.core.mapped_windows.pop(0)
                        self.core.mapped_windows.append(window)
                        self.core.focus_window(self.core.mapped_windows[-1])
                        return

                if keysym == xkb.keysym_from_name("q"):
                    surface = self.core.seat.keyboard_state.focused_surface
                    if surface is not None:
                        if surface.is_xdg_surface:
                            surface = XdgSurface.from_surface(surface)
                            surface.send_close()
                        elif surface.is_xwayland_surface:
                            surface = xwayland.Surface.from_wlr_surface(surface)
                            surface.close()
                    return

                if keysym == xkb.keysym_from_name("1"):
                    self.core.backend.get_session().change_vt(1)
                    return

        log.debug("Key emitted to focused client")
        self.core.seat.set_keyboard(self.device)
        self.core.seat.keyboard_notify_key(key_event)

    def _on_modifiers(self, _listener: Listener, _data: Any):
        log.debug("Signal: wlr_keyboard_modifiers_event")
        self.core.seat.set_keyboard(self.device)
        self.core.seat.keyboard_notify_modifiers(self.keyboard.modifiers)
