import fitz
import numpy as np
import cv2

from paddleocr import PaddleOCR


# Lightweight OCR instance used only for fallback fields
targeted_ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)


def render_pdf_page(pdf_path, page_number=0, scale=3.0):
    """
    Render one PDF page at higher resolution.
    """

    document = fitz.open(str(pdf_path))

    try:
        page = document.load_page(page_number)

        matrix = fitz.Matrix(scale, scale)

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False
        )

        image = np.frombuffer(
            pixmap.samples,
            dtype=np.uint8
        )

        image = image.reshape(
            pixmap.height,
            pixmap.width,
            pixmap.n
        )

        if pixmap.n == 4:
            image = cv2.cvtColor(
                image,
                cv2.COLOR_RGBA2BGR
            )

        elif pixmap.n == 3:
            image = cv2.cvtColor(
                image,
                cv2.COLOR_RGB2BGR
            )

        return image

    finally:
        document.close()

def test_dob_crop(pdf_path):

    image = render_pdf_page(
        pdf_path,
        page_number=0,
        scale=3.0
    )

    height, width = image.shape[:2]

    print(
        "Rendered page:",
        width,
        "x",
        height
    )

    # DOB is on the right side of Section C.
    #
    # These are proportional coordinates rather than
    # hardcoded rendered pixels, so they still work
    # when the rendering scale changes.

    # Crop ONLY the DOB value boxes.
    # Excludes Age, "Date of Birth:" label,
    # and relationship options below.

    # DOB field based on PPStructure coordinates
    x1 = int(width * 0.64)
    x2 = int(width * 0.975)

    y1 = int(height * 0.57)
    y2 = int(height * 0.625)

    crop = image[
        y1:y2,
        x1:x2
    ]
    # Remove the "Date of Birth:" label.
    # Keep only the boxed DOB value.
    crop_width = crop.shape[1]

    value_crop = crop[
    :,
    int(crop_width * 0.42):
]

    cv2.imwrite(
     "dob_crop_debug.png",
    value_crop
    )

    print(
        "DOB crop saved:",
        crop.shape
    )

    return value_crop

def read_targeted_crop(crop):

    if crop is None or crop.size == 0:
        return None

    # Enlarge the small crop
    enlarged = cv2.resize(
        crop,
        None,
        fx=2.0,
        fy=2.0,
        interpolation=cv2.INTER_CUBIC
    )

    # Convert to grayscale
    gray = cv2.cvtColor(
        enlarged,
        cv2.COLOR_BGR2GRAY
    )

    # Improve contrast
    gray = cv2.equalizeHist(gray)

    # Save only for testing
    cv2.imwrite(
        "dob_crop_enhanced.png",
        gray
    )

    result = targeted_ocr.ocr(
        gray,
        cls=False
    )

    texts = []

    if result:

        for page in result:

            if not page:
                continue

            for line in page:

                if (
                    isinstance(line, (list, tuple))
                    and len(line) >= 2
                    and isinstance(line[1], (list, tuple))
                    and len(line[1]) >= 1
                ):

                    text = str(
                        line[1][0]
                    ).strip()

                    if text:
                        texts.append(text)

    print("\n=== TARGETED DOB OCR ===")

    for text in texts:
        print(repr(text))

    return " ".join(texts)

if __name__ == "__main__":

    crop = test_dob_crop(
        r"uploads\claim_form 2.pdf"
    )

    text = read_targeted_crop(crop)

    print("\nCOMBINED:")
    print(text)