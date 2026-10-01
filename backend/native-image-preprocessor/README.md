# QuotePilot native image preprocessor

This Rust executable is an optional accelerator for the CPU-bound part of
product photo recognition. It reads JPEG, PNG, or WebP bytes from stdin and
writes EXIF-oriented, aspect-preserving JPEG bytes to stdout.

Python remains the source of truth for upload validation, model calls,
telemetry, timeouts, and fallback. It enables this executable only when
`NATIVE_IMAGE_PREPROCESSOR_PATH` is configured; an unavailable, timed-out, or
invalid helper result falls back to Pillow automatically.

Build a release executable on the same OS/architecture as the API deployment:

```sh
cargo build --release
```

Set these Railway environment variables after the executable is packaged into
the backend image:

```text
NATIVE_IMAGE_PREPROCESSOR_PATH=/app/bin/quotepilot-image-preprocessor
NATIVE_IMAGE_PREPROCESS_TIMEOUT=15
IMAGE_PREPROCESS_MAX_WORKERS=2
```

Do not point a Linux Railway service at a Windows `.exe`. The helper is
deliberately a child process so its crashes and decoder faults cannot take down
the FastAPI process.
