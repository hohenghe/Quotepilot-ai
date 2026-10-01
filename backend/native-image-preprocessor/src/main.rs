//! Native stdin/stdout image preprocessor for QuotePilot product recognition.
//!
//! Input: original image bytes on stdin.
//! Output: EXIF-oriented, aspect-preserving JPEG bytes on stdout.
//! The Python caller supplies `--max-dimension` and `--quality` and retains
//! responsibility for MIME validation, telemetry, timeouts, and fallback.

use std::env;
use std::io::{self, Read, Write};
use std::process::ExitCode;

use image::codecs::jpeg::JpegEncoder;
use image::imageops::FilterType;
use image::ImageReader;

fn argument(name: &str) -> Result<u32, String> {
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == name {
            return args
                .next()
                .ok_or_else(|| format!("missing value for {name}"))?
                .parse::<u32>()
                .map_err(|_| format!("invalid value for {name}"));
        }
    }
    Err(format!("missing {name}"))
}

fn run() -> Result<(), String> {
    let max_dimension = argument("--max-dimension")?;
    let quality = argument("--quality")?;
    if max_dimension == 0 || quality == 0 || quality > 100 {
        return Err("invalid dimensions or JPEG quality".to_owned());
    }

    let mut input = Vec::new();
    io::stdin()
        .read_to_end(&mut input)
        .map_err(|error| format!("read stdin: {error}"))?;

    let reader = ImageReader::new(io::Cursor::new(input))
        .with_guessed_format()
        .map_err(|error| format!("detect image format: {error}"))?;
    let orientation = reader
        .orientation()
        .map_err(|error| format!("read EXIF orientation: {error}"))?;
    let mut image = reader
        .decode()
        .map_err(|error| format!("decode image: {error}"))?;
    image.apply_orientation(orientation);

    let (width, height) = (image.width(), image.height());
    if width == 0 || height == 0 {
        return Err("decoded image has zero dimensions".to_owned());
    }
    if width.max(height) > max_dimension {
        let scale = max_dimension as f64 / width.max(height) as f64;
        let target_width = (width as f64 * scale).floor().max(1.0) as u32;
        let target_height = (height as f64 * scale).floor().max(1.0) as u32;
        image = image.resize_exact(target_width, target_height, FilterType::Lanczos3);
    }

    let mut stdout = io::BufWriter::new(io::stdout().lock());
    let mut encoder = JpegEncoder::new_with_quality(&mut stdout, quality as u8);
    encoder
        .encode_image(&image)
        .map_err(|error| format!("encode JPEG: {error}"))?;
    stdout.flush().map_err(|error| format!("flush stdout: {error}"))?;
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("native image preprocessing failed: {error}");
            ExitCode::FAILURE
        }
    }
}
