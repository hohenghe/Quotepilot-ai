# Optional C++ image preprocessor

`image_preprocess.cpp` is a libvips based image processor. It builds as a
shared library, avoiding a process startup on every image, or as an executable
using the same stdin/argument/stdout protocol as the existing Rust helper.
Python only sends oversized RGB/grayscale JPEG images to it. All other images
and failed native operations use the established Pillow path. The default is
Pillow.

Build on the Linux machine or container that runs the backend:

```sh
mkdir -p build
g++ -std=c++17 -O3 -fPIC -shared -DQP_LIBRARY_ONLY image_preprocess.cpp -o build/libqp_image.so $(pkg-config --cflags --libs vips)
g++ -std=c++17 -O3 image_preprocess.cpp -o build/qp_image $(pkg-config --cflags --libs vips)
```

The command needs the libvips development package; the executable also needs
the libvips runtime. The application does not require the binary to start. On
Northflank, compile it in the backend build environment and set
`NATIVE_IMAGE_PREPROCESSOR_LIBRARY` to the absolute path of `libqp_image.so`.
The executable can instead be selected with `NATIVE_IMAGE_PREPROCESSOR_PATH`.
The backend Dockerfile builds this library on Linux, runs its EXIF/dimension
integration tests, and checks its runtime dependencies. On Northflank, select
Dockerfile `/backend/Dockerfile` with build context `/backend`. The image does
not enable the library automatically: leave both native variables unset until
CPU/latency measurements and a production-like OCR accuracy benchmark pass.
The shared library was faster in local photo tests because it avoids starting
a subprocess for each image; production gains are not yet verified.

To build and check the image locally on a machine with Docker:

```sh
docker build -f backend/Dockerfile -t quotepilot-backend-native backend
docker run --rm --entrypoint ldd quotepilot-backend-native /app/native-cpp/build/libqp_image.so
docker run --rm --entrypoint python quotepilot-backend-native -c "import ctypes; ctypes.CDLL('/app/native-cpp/build/libqp_image.so')"
```

After verifying real product photos on a staging deployment, set the runtime
variable `NATIVE_IMAGE_PREPROCESSOR_LIBRARY` to
`/app/native-cpp/build/libqp_image.so` to opt in. The C++ path only processes
oversized RGB/grayscale JPEGs; other images continue using Pillow. To roll
back, remove this variable and restart/redeploy the service. For an oversized
JPEG recognition request, check the `[PRODUCT_AI]` log line for
`preprocess_backend=native`; `pillow` means the native path was skipped or
failed, and `original` means no transform was needed. Do not set the older
`NATIVE_IMAGE_PREPROCESSOR_PATH` unless intentionally using the separate
subprocess helper.

After building on Linux, verify the actual binary before enabling it:

```sh
QP_TEST_NATIVE_IMAGE_LIBRARY="$PWD/build/libqp_image.so" python -m pytest ../tests/test_cpp_native_image.py -q
```
