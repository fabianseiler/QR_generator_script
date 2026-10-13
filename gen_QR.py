from pathlib import Path

import qrcode
from PIL import Image, ImageOps


# -----------------------------
# Configuration
# -----------------------------
WEBSITE_URL = "https://eclectx.org/Publications/C80.pdf"
CENTER_IMAGE = "eclectX.png"

# Final PDF output
OUTPUT_FILE = "qr_code_with_logo.pdf"

# High-resolution settings
QR_BOX_SIZE = 60
PDF_DPI = 600

LOGO_SIZE_RATIO = 0.3

# White padding between the logo artwork and the border
LOGO_PADDING = 0

# Small black border around the center image
LOGO_BORDER_WIDTH = 0

# Optional extra white padding outside the black border
# to keep the QR easier to scan
LOGO_OUTER_WHITE_PADDING = 0

# How different a pixel must be from the background
# before it is considered foreground.
FOREGROUND_TOLERANCE = 35

# Alpha cutoff for transparent images
ALPHA_THRESHOLD = 10


def estimate_background_color(
    image: Image.Image,
    border_size: int = 10,
) -> tuple[int, int, int]:
    """
    Estimate the background color by averaging pixels
    along the outer border of the image.
    """
    image = image.convert("RGBA")

    width, height = image.size
    pixels = image.load()

    samples = []

    for y in range(height):
        for x in range(width):
            if (
                x < border_size
                or x >= width - border_size
                or y < border_size
                or y >= height - border_size
            ):
                r, g, b, a = pixels[x, y]

                if a > ALPHA_THRESHOLD:
                    samples.append((r, g, b))

    if not samples:
        return (255, 255, 255)

    avg_r = sum(p[0] for p in samples) // len(samples)
    avg_g = sum(p[1] for p in samples) // len(samples)
    avg_b = sum(p[2] for p in samples) // len(samples)

    return (avg_r, avg_g, avg_b)


def build_foreground_mask(
    image: Image.Image,
    tolerance: int = FOREGROUND_TOLERANCE,
) -> Image.Image:
    """
    Detect the foreground based on its difference from
    the estimated background color.

    Foreground = white (255)
    Background = black (0)
    """
    image = image.convert("RGBA")

    width, height = image.size
    pixels = image.load()

    bg_r, bg_g, bg_b = estimate_background_color(image)

    print(
        f"Detected background color: "
        f"({bg_r}, {bg_g}, {bg_b})"
    )

    mask = Image.new(
        "L",
        (width, height),
        0,
    )

    mask_pixels = mask.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            if a <= ALPHA_THRESHOLD:
                continue

            color_distance = (
                abs(r - bg_r)
                + abs(g - bg_g)
                + abs(b - bg_b)
            )

            if color_distance > tolerance:
                mask_pixels[x, y] = 255

    return mask


def crop_and_square_mask(
    mask: Image.Image,
) -> Image.Image:
    """
    Find the maximum foreground pixel positions on all sides,
    crop to those bounds, then add empty pixels to the shorter
    dimension to produce a perfectly square image.
    """
    bbox = mask.getbbox()

    if bbox is None:
        raise ValueError(
            "No foreground was detected. "
            "Try lowering FOREGROUND_TOLERANCE."
        )

    left, top, right, bottom = bbox

    print("Detected foreground bounds:")
    print(f"  Left:   {left}")
    print(f"  Top:    {top}")
    print(f"  Right:  {right}")
    print(f"  Bottom: {bottom}")

    cropped = mask.crop(bbox)

    width, height = cropped.size

    print(
        f"Detected content dimensions: "
        f"{width} x {height}"
    )

    square_size = max(width, height)

    horizontal_difference = square_size - width
    vertical_difference = square_size - height

    pad_left = horizontal_difference // 2
    pad_right = horizontal_difference - pad_left

    pad_top = vertical_difference // 2
    pad_bottom = vertical_difference - pad_top

    squared = ImageOps.expand(
        cropped,
        border=(
            pad_left,
            pad_top,
            pad_right,
            pad_bottom,
        ),
        fill=0,
    )

    print(
        f"Squared logo dimensions: "
        f"{squared.width} x {squared.height}"
    )

    return squared


def render_mask_as_black_on_white(
    mask: Image.Image,
) -> Image.Image:
    """
    Convert the foreground mask into pure black line art
    on a pure white background.
    """
    output = Image.new(
        "L",
        mask.size,
        255,
    )

    black = Image.new(
        "L",
        mask.size,
        0,
    )

    output.paste(
        black,
        (0, 0),
        mask,
    )

    return output


def prepare_center_image(
    image_path: str,
    target_size: int,
) -> Image.Image:
    """
    Detect foreground, crop it, square it, resize it,
    and convert it to pure black and white.
    """
    original = Image.open(image_path)

    print(
        f"Original logo dimensions: "
        f"{original.width} x {original.height}"
    )

    mask = build_foreground_mask(original)

    squared_mask = crop_and_square_mask(mask)

    resized_mask = squared_mask.resize(
        (target_size, target_size),
        Image.Resampling.LANCZOS,
    )

    # Re-binarize after resize
    resized_mask = resized_mask.point(
        lambda p: 255 if p >= 128 else 0
    )

    return render_mask_as_black_on_white(
        resized_mask
    )


def create_qr_with_center_image(
    url: str,
    center_image_path: str,
    output_path: str,
) -> None:

    # -----------------------------
    # Create high-resolution QR
    # -----------------------------
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=QR_BOX_SIZE,
        border=4,
    )

    qr.add_data(url)
    qr.make(fit=True)

    qr_image = qr.make_image(
        fill_color="black",
        back_color="white",
    ).convert("RGBA")

    qr_width, qr_height = qr_image.size

    print(
        f"High-resolution QR dimensions: "
        f"{qr_width} x {qr_height} px"
    )

    # -----------------------------
    # Prepare center image
    # -----------------------------
    target_logo_size = int(
        min(qr_width, qr_height)
        * LOGO_SIZE_RATIO
    )

    logo = prepare_center_image(
        center_image_path,
        target_logo_size,
    )

    # White padding around logo artwork
    logo = ImageOps.expand(
        logo,
        border=LOGO_PADDING,
        fill=255,
    )

    # Small black border around the padded logo
    logo = ImageOps.expand(
        logo,
        border=LOGO_BORDER_WIDTH,
        fill=0,
    )

    # Optional outer white padding so the border does not
    # sit directly against QR modules
    logo = ImageOps.expand(
        logo,
        border=LOGO_OUTER_WHITE_PADDING,
        fill=255,
    )

    logo = logo.convert("RGBA")

    # -----------------------------
    # Center logo
    # -----------------------------
    logo_width, logo_height = logo.size

    x = (qr_width - logo_width) // 2
    y = (qr_height - logo_height) // 2

    qr_image.alpha_composite(
        logo,
        dest=(x, y),
    )

    # -----------------------------
    # Force entire result to pure B/W
    # -----------------------------
    final_image = qr_image.convert("L")
    final_image = final_image.point(
        lambda p: 255 if p >= 128 else 0
    )

    pdf_image = final_image.convert("RGB")

    # -----------------------------
    # Save as PDF
    # -----------------------------
    pdf_image.save(
        output_path,
        format="PDF",
        resolution=PDF_DPI,
    )

    print()
    print("Finished.")
    print(f"PDF: {output_path}")
    print(f"Destination URL: {url}")
    print(
        f"Raster resolution: "
        f"{qr_width} x {qr_height} pixels"
    )
    print(f"PDF resolution: {PDF_DPI} DPI")

    physical_width = qr_width / PDF_DPI
    physical_height = qr_height / PDF_DPI

    print(
        f"Approximate PDF physical size: "
        f"{physical_width:.2f} x "
        f"{physical_height:.2f} inches"
    )


if __name__ == "__main__":

    if not Path(CENTER_IMAGE).exists():
        raise FileNotFoundError(
            f"Center image not found: "
            f"{CENTER_IMAGE}"
        )

    create_qr_with_center_image(
        WEBSITE_URL,
        CENTER_IMAGE,
        OUTPUT_FILE,
    )