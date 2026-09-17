from paddleocr import PPStructureV3
from pathlib import Path
import pymupdf
import tempfile
import time
import os
import re


# =========================================================
# CLAIM FORM PRECHECK
# =========================================================

def is_claim_form_pdf(file_path):

    """
    Cheap pre-check using embedded PDF text.

    This runs BEFORE PaddleOCR so we can decide whether
    expensive table recognition is necessary.

    Returns True only when there are strong claim-form
    signals. Otherwise False.
    """

    try:

        document = pymupdf.open(
            str(file_path)
        )

        text_parts = []

        # Read embedded text from all pages.
        # This is normally very fast.
        for page in document:

            text_parts.append(
                page.get_text("text") or ""
            )

        document.close()


        full_text = " ".join(
            text_parts
        ).lower()


        full_text = re.sub(
            r"\s+",
            " ",
            full_text
        ).strip()


        compact_text = re.sub(
            r"[^a-z0-9]+",
            "",
            full_text
        )


        # ---------------------------------------------
        # Strong claim-form signals
        # ---------------------------------------------

        signals = [
            "claimform",
            "claimsreimbursementform",
            "claimreimbursementform",
            "detailsofprimaryinsured",
            "detailsofinsured",
            "detailsofhospitalization",
            "totalamountofclaim",
            "totalamountofclaims",
            "membergeneralinformation",
            "declarationbytheinsured",
        ]


        hits = sum(
            signal in compact_text
            for signal in signals
        )


        print(
            f"PDF claim-form precheck: "
            f"{hits} signal(s)",
            flush=True
        )


        # Require multiple signals so an invoice that
        # merely contains the word "claim" is NOT
        # accidentally routed to the lightweight path.
        return hits >= 2


    except Exception as error:

        print(
            "PDF precheck failed:",
            error,
            flush=True
        )

        # SAFETY:
        # Unknown PDFs use the full pipeline.
        return False


# =========================================================
# FULL PIPELINE
#
# Used for:
# - invoices
# - receipts
# - images
# - unknown PDFs
#
# Tables ON.
# =========================================================

print(
    "Initializing full PPStructureV3 pipeline..."
)

_full_start = time.perf_counter()


full_pipeline = PPStructureV3(
    lang="en",

    enable_mkldnn=True,
    cpu_threads=4,

    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,

    use_table_recognition=True,
    use_region_detection=True,

    use_formula_recognition=False,
    use_chart_recognition=False,
    use_seal_recognition=False,
)


print(
    "Full PPStructureV3 initialized in "
    f"{time.perf_counter() - _full_start:.2f}s"
)


# =========================================================
# LIGHT CLAIM-FORM PIPELINE
#
# IMPORTANT:
# Initialize lazily.
#
# We don't create it until the first claim form arrives.
# =========================================================

claim_form_pipeline = None


def get_claim_form_pipeline():

    global claim_form_pipeline


    if claim_form_pipeline is not None:

        return claim_form_pipeline


    print(
        "Initializing claim-form pipeline...",
        flush=True
    )


    start = time.perf_counter()


    claim_form_pipeline = PPStructureV3(
        lang="en",

        enable_mkldnn=True,
        cpu_threads=4,

        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,

        # MAIN PERFORMANCE DIFFERENCE
        use_table_recognition=False,

        use_region_detection=True,

        use_formula_recognition=False,
        use_chart_recognition=False,
        use_seal_recognition=False,
    )


    print(
        "Claim-form pipeline initialized in "
        f"{time.perf_counter() - start:.2f}s",
        flush=True
    )


    return claim_form_pipeline


# =========================================================
# PARSE DOCUMENT
# =========================================================

def parse_document(file_path):

    start = time.perf_counter()

    file_path = Path(
        file_path
    )

    structured_results = []

    temp_files = []


    try:

        # =================================================
        # PDF
        # =================================================

        if file_path.suffix.lower() == ".pdf":

            # ---------------------------------------------
            # CHEAP PRE-CLASSIFICATION
            # ---------------------------------------------

            claim_form_mode = (
                is_claim_form_pdf(
                    file_path
                )
            )


            if claim_form_mode:

                print(
                    "Routing PDF -> CLAIM FORM pipeline "
                    "(tables OFF)",
                    flush=True
                )

                selected_pipeline = (
                    get_claim_form_pipeline()
                )

            else:

                print(
                    "Routing PDF -> FULL pipeline "
                    "(tables ON)",
                    flush=True
                )

                selected_pipeline = (
                    full_pipeline
                )


            # ---------------------------------------------
            # Render PDF at 150 DPI
            # ---------------------------------------------

            print(
                "PDF detected - rendering at 150 DPI",
                flush=True
            )


            document = pymupdf.open(
                str(file_path)
            )


            try:

                for page_number in range(
                    document.page_count
                ):

                    page_start = (
                        time.perf_counter()
                    )


                    page = document.load_page(
                        page_number
                    )


                    zoom = 150 / 72


                    matrix = pymupdf.Matrix(
                        zoom,
                        zoom
                    )


                    pixmap = page.get_pixmap(
                        matrix=matrix,
                        alpha=False
                    )


                    temp_file = (
                        tempfile.NamedTemporaryFile(
                            suffix=".png",
                            delete=False
                        )
                    )


                    temp_path = (
                        temp_file.name
                    )


                    temp_file.close()


                    pixmap.save(
                        temp_path
                    )


                    temp_files.append(
                        temp_path
                    )


                    print(
                        f"Processing PDF page "
                        f"{page_number + 1}/"
                        f"{document.page_count}",
                        flush=True
                    )


                    results = (
                        selected_pipeline.predict(
                            temp_path
                        )
                    )


                    page_results = [
                        result.json
                        for result in results
                    ]


                    structured_results.extend(
                        page_results
                    )


                    print(
                        f"Page {page_number + 1}: "
                        f"{time.perf_counter() - page_start:.2f}s",
                        flush=True
                    )


            finally:

                document.close()


        # =================================================
        # IMAGE
        # =================================================
        #
        # Your rich invoices / blurred Apollo are images.
        # Keep them on the known-good full pipeline.
        # =================================================

        else:

            print(
                "Routing image -> FULL pipeline "
                "(tables ON)",
                flush=True
            )


            results = full_pipeline.predict(
                str(file_path)
            )


            structured_results = [
                result.json
                for result in results
            ]


        # =================================================
        # TOTAL
        # =================================================

        elapsed = (
            time.perf_counter()
            - start
        )


        print(
            f"PPStructure total: {elapsed:.2f}s",
            flush=True
        )


        return structured_results


    finally:

        # =================================================
        # CLEAN TEMPORARY PDF IMAGES
        # =================================================

        for temp_path in temp_files:

            try:

                if os.path.exists(
                    temp_path
                ):

                    os.remove(
                        temp_path
                    )


            except Exception as error:

                print(
                    "Temporary file cleanup:",
                    error,
                    flush=True
                )