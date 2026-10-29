# KaiCamp LivePortrait adapter — experimental

This is the first backend adapter for the existing KaiCamp / Face-Puppet project.
It does not replace the current GitHub Pages app and must not be deployed as a
public unauthenticated endpoint.

## Current milestone

- Accept a source portrait and a short camera-recorded driving video.
- Call the official LivePortrait `inference.py` script.
- Return an MP4 result.
- Require a bearer token and enforce upload size limits.

**Not yet real-time:** this is a photo + recorded driving-video workflow. It does
not stream frames continuously, does not yet provide low-latency live-call output,
and does not guarantee a clean stationary background in every generated result.
LivePortrait's stock inference may create a comparison/concatenated video; inspect
the output before treating it as the final avatar-only feed.

## Runtime requirements

The container here is only the HTTP adapter. The host must provide:
- A supported Python/PyTorch environment for the official LivePortrait project.
- The official LivePortrait source and pretrained weights under `/opt/LivePortrait`.
- FFmpeg and, preferably, an NVIDIA GPU with compatible CUDA/PyTorch packages.
- Persistent storage for temporary output, plus TLS at the public ingress.

Follow the official setup instructions at:
https://github.com/KlingAIResearch/LivePortrait

## Environment

- `LIVEPORTRAIT_HOME`: default `/opt/LivePortrait`
- `KAICAMP_API_TOKEN`: required random secret; without it `POST /animate` returns 503
- `MAX_UPLOAD_BYTES`: per-file limit, default 30 MiB
- `INFERENCE_TIMEOUT_SECONDS`: default 240
- `PYTHON`: Python executable used for inference, default `python`

## API

- `GET /health`: reports whether the inference script exists; it does not prove model weights or GPU inference work.
- `POST /animate`: multipart fields `source` (portrait image) and `driving` (MP4/MOV/WEBM). Header: `Authorization: Bearer <KAICAMP_API_TOKEN>`. Returns an MP4.

## Important integration boundary

The current `index.html` uses MediaPipe to track landmarks and translate a segmented person cut-out. It does not currently call this service. Do not add a production API URL to the public page until a GPU-backed deployment is running, authenticated, tested with a sample portrait/video, and its returned video format has been confirmed.

## Next engineering steps

1. Run the official LivePortrait inference on a sample portrait + 3–5 second camera clip in a GPU environment.
2. Confirm the exact output artifact and whether the generated portrait can be extracted without comparison panels.
3. Deploy this adapter only behind HTTPS and with a strong token; use short-lived auth or a server-side proxy before any public release.
4. Integrate a visible “Generate test animation” workflow in KaiCamp.
5. Separately engineer a persistent GPU frame-streaming pipeline for actual real-time video calls. The current batch endpoint is not suitable as a live virtual camera.
