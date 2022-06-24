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
from typing import Any

from pywayland.server import Listener
from wlroots.wlr_types import InputDevice
from xkbcommon import xkb

from libnext.util import Listeners

log = logging.getLogger("Next: Inputs")


class NextKeyboard(Listeners):
    def __init__(self, core, device: InputDevice):
        self.device = device
        self.keyboard = device.keyboard
        self.core = core

        # NOTE: https://github.com/Shinyzenith/NextWM/issues/5
        self.keyboard.set_repeat_info(100, 300)
        self.xkb_context = xkb.Context()

        # TODO: Bind more listeners.
        self.add_listener(self.keyboard.destroy_event, self._on_destroy)

    def destroy(self) -> None:
        self.destroy_listeners()
        self.core.keyboards.remove(self)
        if self.core.keyboards and self.core.seat.keyboard.destroyed:
            self.seat.set_keyboard(self.core.keyboards[-1].device)

    # Listeners
    def _on_destroy(self, listener: Listener, _: Any) -> None:
        log.info("Signal: wlr_keyboard_destroy_event")
        self.destroy()
