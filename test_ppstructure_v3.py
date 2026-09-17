from app.services.document_parser_v3 import parse_document
from app.services.claim_extractor_v3 import extract_rich_total_amount_v3


file_path = r"uploads\receipt2.png"

structured_results = parse_document(file_path)


def print_receipt_debug(obj):

    if isinstance(obj, dict):

        block = obj.get("block_content")

        if isinstance(block, str) and block.strip():
            print("\n--- BLOCK CONTENT ---")
            print(repr(block))

        rec_texts = obj.get("rec_texts")

        if isinstance(rec_texts, list):

            print("\n--- REC TEXTS ---")

            for text in rec_texts:
                print(repr(text))

        for value in obj.values():
            print_receipt_debug(value)

    elif isinstance(obj, list):

        for item in obj:
            print_receipt_debug(item)


print("\n============================")
print("RECEIPT 2 OCR DEBUG")
print("============================")

print_receipt_debug(
    structured_results
)

raise SystemExit

def print_structure(obj, depth=0):

    if depth > 3:
        return

    indent = "  " * depth

    if isinstance(obj, dict):

        for key, value in obj.items():

            print(
                f"{indent}{key}: "
                f"{type(value).__name__}"
            )

            if isinstance(value, (dict, list)):
                print_structure(
                    value,
                    depth + 1
                )

    elif isinstance(obj, list):

        for index, item in enumerate(obj[:3]):

            print(
                f"{indent}[{index}]: "
                f"{type(item).__name__}"
            )

            if isinstance(item, (dict, list)):
                print_structure(
                    item,
                    depth + 1
                )


print_structure(structured_results)

def print_block_content(obj):

    if isinstance(obj, dict):

        value = obj.get("block_content")

        if isinstance(value, str) and value.strip():

            print("\n--- BLOCK ---")
            print(value)

        for child in obj.values():
            print_block_content(child)

    elif isinstance(obj, list):

        for child in obj:
            print_block_content(child)


print("\n=== RICH INVOICE BLOCK CONTENT ===")

print_block_content(structured_results)

def print_text_and_boxes(obj):

    if isinstance(obj, dict):

        if "rec_texts" in obj and "rec_boxes" in obj:

            texts = obj["rec_texts"]
            boxes = obj["rec_boxes"]

            print("\n===== TEXT + POSITION =====")

            for text, box in zip(texts, boxes):
                print(f"{text!r} -> {box}")

        for value in obj.values():
            print_text_and_boxes(value)

    elif isinstance(obj, list):

        for item in obj:
            print_text_and_boxes(item)

print_text_and_boxes(structured_results)

def debug_search(obj, targets):

    if isinstance(obj, dict):

        for key, value in obj.items():

            if isinstance(value, str):

                lower = value.lower()

                if any(
                    target.lower() in lower
                    for target in targets
                ):
                    print(
                        "KEY:",
                        key,
                        "VALUE:",
                        repr(value)
                    )

            debug_search(value, targets)

    elif isinstance(obj, list):

        for item in obj:
            debug_search(item, targets)

print("\n=== SEARCHING DOB + DISCHARGE ===")

debug_search(
    structured_results,
    [
        "20/05/2018",
        "20/5/2018",
        "20052018",
        "20 05 2018",
        "13/07/2026",
        "13/7/2026",
        "13072026",
        "13 07 2026",
        "Date of Birth",
        "Date of Discharge"
    ]
)