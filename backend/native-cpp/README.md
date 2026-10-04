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
Keep both variables unset until the target Linux build has passed image
fixtures, CPU/latency measurements, and a production-like OCR accuracy
benchmark. The shared library is faster in local photo tests because it avoids
starting a subprocess for each image.

After building on Linux, verify the actual binary before enabling it:

```sh
QP_TEST_NATIVE_IMAGE_LIBRARY="$PWD/build/libqp_image.so" python -m pytest ../tests/test_cpp_native_image.py -q
```
