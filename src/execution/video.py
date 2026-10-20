"""Stream native-step RGB to FFmpeg; never retain an episode in memory."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def encoder_executable():
    executable = shutil.which('ffmpeg')
    if executable is None:
        try:
            import imageio_ffmpeg
            executable = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError) as exc:
            raise RuntimeError('Video recording requires ffmpeg or imageio-ffmpeg in the simulation '
                               'environment; use --no-save-video to disable recording') from exc
    return executable


def check_encoder():
    executable = encoder_executable()
    result = subprocess.run([executable, '-hide_banner', '-encoders'], capture_output=True,
                            text=True, check=True, timeout=15)
    if 'libx264' not in result.stdout:
        raise RuntimeError('Video recording requires an FFmpeg build with libx264')
    return executable


class EpisodeVideo:
    """One initial frame, then one frame per completed native control step.

    Only a successfully finalized file is renamed to episode.mp4. Encoding failures
    are recorded separately from the environment's task success.
    """
    def __init__(self, output, image_size, fps, cameras, *, includes_initialization=True):
        self.output = Path(output)
        self.path = self.output / 'episode.mp4'
        self.partial = self.output / 'episode.partial.mp4'
        self.cameras = tuple(cameras)
        self.image_size, self.fps = image_size, float(fps)
        self.includes_initialization = includes_initialization
        self.frames = 0
        self.closed = self.complete = False
        self.error = None
        self.process = self.log = None
        self.frame_shape = (image_size, image_size) if isinstance(image_size, int) else tuple(image_size)
        height, camera_width = self.frame_shape
        width = camera_width * len(self.cameras)
        # yuv420p needs even dimensions: pad, never rescale camera pixels.
        self.width, self.height = width + width % 2, height + height % 2
        for path in (self.path, self.partial, self.output / 'video.json', self.output / 'video_encoder.log'):
            if path.exists():
                raise ValueError(f'refusing to overwrite video artifact: {path}')
        executable = check_encoder()
        self.log = (self.output / 'video_encoder.log').open('wb')
        try:
            self.process = subprocess.Popen([
                executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s:v', f'{width}x{height}',
                '-r', str(self.fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
                '-preset', 'veryfast', '-crf', '18', '-threads', '1',
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', str(self.partial),
            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log)
        except BaseException:
            self.log.close()
            raise

    def append(self, images):
        if self.closed:
            raise RuntimeError('video already finalized')
        try:
            for image in images:
                if image.dtype != np.uint8 or image.shape != (*self.frame_shape, 3):
                    raise ValueError('invalid video RGB frame')
            if len(images) != len(self.cameras):
                raise ValueError('incorrect video camera count')
            frame = np.ascontiguousarray(np.concatenate(images, axis=1))
            if self.process.poll() is not None:
                raise RuntimeError(f'FFmpeg exited early ({self.process.returncode}); see video_encoder.log')
            self.process.stdin.write(frame.tobytes())
            self.process.stdin.flush()
            self.frames += 1
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            raise RuntimeError(f'episode video recording failed: {self.error}') from exc

    def finish(self):
        if self.closed:
            return self.status()
        self.closed = True
        try:
            try:
                self.process.stdin.close()
            finally:
                code = self.process.wait(timeout=30)
            if code != 0:
                raise RuntimeError(f'FFmpeg exited with code {code}; see video_encoder.log')
            if not self.frames or not self.partial.is_file() or not self.partial.stat().st_size:
                raise RuntimeError('encoder produced no video frames')
            if self.error is None:
                self.partial.replace(self.path)
                self.complete = True
        except Exception as exc:
            self.error = self.error or f'{type(exc).__name__}: {exc}'
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.log.close()
        if self.error:
            print(f'[Codex] video incomplete: {self.error}', file=sys.stderr, flush=True)
        from execution.artifacts import write_json
        write_json(self.output / 'video.json', self.status())
        return self.status()

    def status(self):
        return dict(enabled=True, complete=self.complete,
                    path=str(self.path if self.complete else self.partial),
                    frames=self.frames, fps=self.fps, duration_seconds=self.frames / self.fps,
                    width=self.width, height=self.height, cameras=list(self.cameras),
                    layout='horizontal', includes_initial_frame=True,
                    includes_initialization=self.includes_initialization, error=self.error)
