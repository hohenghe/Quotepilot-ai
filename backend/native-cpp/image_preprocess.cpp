#include <vips/vips.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <iterator>
#include <mutex>
#include <string>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#define QP_EXPORT extern "C" __declspec(dllexport)
#else
#define QP_EXPORT extern "C" __attribute__((visibility("default")))
#endif

namespace {
std::once_flag init_once;
bool vips_ready = false;

void initialize() {
    std::call_once(init_once, [] {
        vips_ready = vips_init("quotepilot-image") == 0;
        if (vips_ready) {
            // Python already bounds concurrent calls to the native library.
            vips_concurrency_set(1);
            vips_cache_set_max(0);
        }
    });
}

int process_image(const char* input, std::size_t input_size, int max_dimension,
                  int quality, void** output, std::size_t* output_size) {
    if (!input || !output || !output_size || input_size == 0 ||
        input_size > 5 * 1024 * 1024 || max_dimension < 1 ||
        max_dimension > 8192 || quality < 1 || quality > 100) return -1;
    *output = nullptr;
    *output_size = 0;
    initialize();
    if (!vips_ready) return -1;

    VipsImage* source = vips_image_new_from_buffer(
        const_cast<char*>(input), input_size, "", nullptr);
    if (!source) return -1;
    VipsImage* thumbnail = nullptr;
    int result = -1;
    do {
        const auto width = vips_image_get_width(source);
        const auto height = vips_image_get_height(source);
        if (width < 1 || height < 1 ||
            static_cast<std::int64_t>(width) * height > 100000000) break;
        // Python only dispatches ordinary RGB/grayscale JPEGs here.
        if (vips_image_get_format(source) != VIPS_FORMAT_UCHAR ||
            (vips_image_get_bands(source) != 1 &&
             vips_image_get_bands(source) != 3)) break;
        // Uses JPEG shrink-on-load, then Lanczos3; EXIF orientation is applied.
        if (vips_thumbnail_buffer(const_cast<char*>(input), input_size,
                &thumbnail, max_dimension, "height", max_dimension,
                "size", VIPS_SIZE_DOWN, nullptr)) break;
        if (vips_jpegsave_buffer(thumbnail, output, output_size,
                "Q", quality, "strip", TRUE, nullptr)) break;
        result = 0;
    } while (false);

    if (thumbnail) g_object_unref(thumbnail);
    g_object_unref(source);
    if (result != 0 && *output) {
        g_free(*output);
        *output = nullptr;
        *output_size = 0;
    }
    return result;
}
}  // namespace

QP_EXPORT int qp_preprocess_image(const char* input, std::size_t input_size,
                                   int max_dimension, int quality,
                                   void** output, std::size_t* output_size) noexcept {
    try {
        return process_image(input, input_size, max_dimension, quality,
                             output, output_size);
    } catch (...) {
        return -1;
    }
}

QP_EXPORT void qp_free_image(void* output) noexcept {
    g_free(output);
}

#ifndef QP_LIBRARY_ONLY
int main(int argc, char** argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (argc != 5 || std::string(argv[1]) != "--max-dimension" ||
        std::string(argv[3]) != "--quality") return 2;
    try {
        const int max_dimension = std::stoi(argv[2]);
        const int quality = std::stoi(argv[4]);
        std::istreambuf_iterator<char> end;
        const std::vector<char> input(std::istreambuf_iterator<char>(std::cin), end);
        void* output = nullptr;
        std::size_t output_size = 0;
        if (qp_preprocess_image(input.data(), input.size(), max_dimension,
                                quality, &output, &output_size) != 0) return 1;
        std::cout.write(static_cast<const char*>(output), output_size);
        const bool ok = static_cast<bool>(std::cout);
        qp_free_image(output);
        return ok ? 0 : 1;
    } catch (...) {
        return 2;
    }
}
#endif
