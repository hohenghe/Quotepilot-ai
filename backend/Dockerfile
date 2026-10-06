# syntax=docker/dockerfile:1

# Northflank: Dockerfile /backend/Dockerfile, build context /backend.
# Keep the C++ library opt-in until the Linux image and OCR output are checked.
FROM python:3.12-slim-bookworm AS build

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config libvips-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m venv "$VIRTUAL_ENV" \
    && pip install -r requirements.txt

COPY native-cpp/image_preprocess.cpp ./native-cpp/image_preprocess.cpp
RUN mkdir -p native-cpp/build \
    && g++ -std=c++17 -O3 -fPIC -shared -DQP_LIBRARY_ONLY \
        native-cpp/image_preprocess.cpp \
        -o native-cpp/build/libqp_image.so \
        $(pkg-config --cflags --libs vips)

COPY app ./app
COPY tests/test_cpp_native_image.py ./tests/test_cpp_native_image.py
# Test the actual Linux .so during every image build, without shipping pytest.
RUN pip install --target /tmp/native-test-deps 'pytest>=8,<10' \
    && PYTHONPATH=/tmp/native-test-deps \
       QP_TEST_NATIVE_IMAGE_LIBRARY=/app/native-cpp/build/libqp_image.so \
       python -m pytest tests/test_cpp_native_image.py -q

FROM python:3.12-slim-bookworm

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libvips42 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/app /app/app
COPY --from=build /app/native-cpp/build/libqp_image.so /app/native-cpp/build/libqp_image.so
COPY seed_admin.py ./seed_admin.py
COPY reset_admin_password.py ./reset_admin_password.py

# Catch missing shared-library dependencies before deployment; no feature flag
# is set here, so the production default remains Pillow.
RUN ldd /app/native-cpp/build/libqp_image.so | grep -q libvips \
    && ! ldd /app/native-cpp/build/libqp_image.so | grep -q 'not found' \
    && python -c "import app.main, seed_admin, reset_admin_password"

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
