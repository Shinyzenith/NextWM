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
from wlroots import ffi, lib
from wlroots.wlr_types import InputDevice
from wlroots.wlr_types.keyboard import KeyboardKeyEvent, KeyboardModifier
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
            self.seat.set_keyboard(self.core.keyboards[-1].device)

    # Listeners
    def _on_destroy(self, _listener: Listener, _data: Any) -> None:
        log.info("Signal: wlr_keyboard_destroy_event")
        self.destroy()

    def _on_key(self, _listener: Listener, key_event: KeyboardKeyEvent) -> None:
        log.info("Signal: wlr_keyboard_key_event")
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
            if (
                self.keyboard.modifier == KeyboardModifier.ALT
                and key_event.state == WlKeyboard.key_state.pressed  # noqa
            ):
                if keysym == xkb.keysym_from_name("Escape"):
                    self.core.display.terminate()
                    return
                if keysym == xkb.keysym_from_name("j"):
                    subprocess.Popen(["alacritty"])
                    return

        log.info("Emitting key to focused client.")
        self.core.seat.set_keyboard(self.device)
        self.core.seat.keyboard_notify_key(key_event)

    def _on_modifiers(self, _listener: Listener, _data: Any):
        log.info("Signal: wlr_keyboard_modifiers_event")
        self.core.seat.set_keyboard(self.device)
        self.core.seat.keyboard_notify_modifiers(self.keyboard.modifiers)
