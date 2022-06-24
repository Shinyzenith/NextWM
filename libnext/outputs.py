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

from typing import Any

from pywayland.server import Listener
from wlroots.util.clock import Timespec
from wlroots.wlr_types import OutputDamage

from libnext.util import Listeners


class NextOutput(Listeners):
    def __init__(self, core, wlr_output):
        self.core = core
        self.wlr_output = wlr_output
        self.damage: OutputDamage = OutputDamage(wlr_output)
        self.x, self.y = self.core.output_layout.output_coords(wlr_output)

        wlr_output.data = self

        self.add_listener(wlr_output.destroy_event, self._on_destroy)
        self.add_listener(self.damage.frame_event, self._on_frame)

    def destroy(self) -> None:
        self.core.outputs.remove(self)
        self.destroy_listeners()

    def _on_destroy(self, _listener: Listener, _data: Any) -> None:
        self.destroy()

    def _on_frame(self, _listener: Listener, _data: Any) -> None:
        scene_output = self.core.scene.get_scene_output(self.wlr_output)
        scene_output.commit()
        now = Timespec.get_monotonic_time()
        scene_output.send_frame_done(now)
