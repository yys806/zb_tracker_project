#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace {

using MaskArray = py::array_t<std::uint8_t, py::array::c_style | py::array::forcecast>;

void erode_once(const std::uint8_t* src, std::uint8_t* dst, int height, int width, int radius) {
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            std::uint8_t keep = 255;
            for (int ky = -radius; ky <= radius && keep != 0; ++ky) {
                const int yy = y + ky;
                for (int kx = -radius; kx <= radius; ++kx) {
                    const int xx = x + kx;
                    // Match OpenCV's morphology default: outside pixels do not
                    // shrink a white object during erosion.
                    if (0 <= yy && yy < height && 0 <= xx && xx < width && src[yy * width + xx] == 0) {
                        keep = 0;
                        break;
                    }
                }
            }
            dst[y * width + x] = keep;
        }
    }
}

void dilate_once(const std::uint8_t* src, std::uint8_t* dst, int height, int width, int radius) {
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            std::uint8_t value = 0;
            for (int ky = -radius; ky <= radius && value == 0; ++ky) {
                const int yy = y + ky;
                for (int kx = -radius; kx <= radius; ++kx) {
                    const int xx = x + kx;
                    if (0 <= yy && yy < height && 0 <= xx && xx < width && src[yy * width + xx] > 0) {
                        value = 255;
                        break;
                    }
                }
            }
            dst[y * width + x] = value;
        }
    }
}

MaskArray open_close_mask(MaskArray mask, int kernel_size) {
    if (kernel_size <= 0) {
        throw std::invalid_argument("kernel_size must be positive");
    }

    py::buffer_info info = mask.request();
    if (info.ndim != 2) {
        throw std::invalid_argument("mask must be a 2D uint8 array");
    }

    const int height = static_cast<int>(info.shape[0]);
    const int width = static_cast<int>(info.shape[1]);
    const int radius = kernel_size / 2;
    const auto* input = static_cast<const std::uint8_t*>(info.ptr);

    MaskArray output({height, width});
    py::buffer_info output_info = output.request();
    auto* output_ptr = static_cast<std::uint8_t*>(output_info.ptr);

    const std::size_t total = static_cast<std::size_t>(height) * static_cast<std::size_t>(width);
    std::vector<std::uint8_t> tmp1(total);
    std::vector<std::uint8_t> tmp2(total);
    std::vector<std::uint8_t> tmp3(total);

    erode_once(input, tmp1.data(), height, width, radius);
    dilate_once(tmp1.data(), tmp2.data(), height, width, radius);
    dilate_once(tmp2.data(), tmp3.data(), height, width, radius);
    erode_once(tmp3.data(), output_ptr, height, width, radius);

    return output;
}

}  // namespace

PYBIND11_MODULE(morphology_ext, m) {
    m.doc() = "Binary morphology accelerator for the OrangePi tracking project";
    m.def("open_close_mask", &open_close_mask, py::arg("mask"), py::arg("kernel_size"));
}
