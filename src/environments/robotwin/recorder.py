"""Instance-local physics-step RGB sampling, adapted from the supplied recorder.

The shared video writer owns encoding, partial artifacts and finalization.
"""
import math

import numpy as np
from PIL import Image

from execution.video import EpisodeVideo

CAMERAS = ('head_camera', 'left_camera', 'right_camera')


class PhysicsVideo(EpisodeVideo):
    def __init__(self, task, output, image_size):
        self.task = task
        self.physics_steps = 0
        self.timestep = float(task.scene.get_timestep())
        if not math.isfinite(self.timestep) or self.timestep <= 0:
            raise ValueError('invalid RoboTwin physics timestep')
        self.original_step = task.scene.step
        self.next_frame_time = 1 / 25
        self.call_index = None
        self.last_frame_step = None
        self.hooked = False
        self.timeline = None
        rig = task.cameras
        self.native_cameras = (rig.static_camera_list[rig.static_camera_name.index('head_camera')],
                               rig.left_camera, rig.right_camera)
        super().__init__(output, image_size, 25, CAMERAS, includes_initialization=False)
        try:
            self.timeline = (output / 'video_timeline.jsonl').open('x', encoding='utf-8')
            self._capture_frame()
            task.scene.step = self.step
            self.hooked = True
        except BaseException:
            self.finish()
            raise

    def step(self):
        value = self.original_step()
        self.physics_steps += 1
        seconds = self.physics_steps * self.timestep
        if seconds + 1e-9 >= self.next_frame_time:
            self._capture_frame()
            while self.next_frame_time <= seconds + 1e-9:
                self.next_frame_time += 1 / self.fps
        return value

    def _capture_frame(self):
        try:
            self._write_camera_frame()
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            raise

    def _write_camera_frame(self):
        import json
        self.task._update_render()
        images = []
        for camera in self.native_cameras:
            camera.take_picture()
            color = np.asarray(camera.get_picture('Color'))
            if color.ndim != 3 or color.shape[2] < 3 or not np.isfinite(color).all():
                raise ValueError('invalid video camera RGB')
            rgb = (color[:, :, :3] * 255).clip(0, 255).astype(np.uint8)
            images.append(np.asarray(Image.fromarray(rgb).resize((self.image_size, self.image_size))))
        self.append(images)
        self.timeline.write(json.dumps(dict(frame=self.frames - 1, video_seconds=(self.frames - 1) / self.fps,
            physics_step=self.physics_steps, simulation_seconds=self.physics_steps * self.timestep,
            native_call_index=self.call_index)) + '\n')
        self.last_frame_step = self.physics_steps

    def status(self):
        return dict(super().status(), physics_steps=self.physics_steps,
                    simulation_seconds=self.physics_steps * self.timestep,
                    includes_inference_wait=False, sampling='RGB after actual physics steps')

    def finish(self):
        if self.hooked:
            self.task.scene.step = self.original_step
            self.hooked = False
        try:
            if not self.closed and self.error is None and self.last_frame_step != self.physics_steps:
                try:
                    self._capture_frame()
                except Exception:
                    pass  # The shared writer persists the capture error as an incomplete video.
            return super().finish()
        finally:
            if self.timeline is not None:
                self.timeline.close()
