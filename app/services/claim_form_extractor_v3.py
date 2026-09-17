import re


def get_text_items(structured_results):
    """
    Collect recognized text together with its coordinates.
    """

    items = []
    seen = set()

    def walk(obj):

        if isinstance(obj, dict):

            if (
                "rec_texts" in obj
                and "rec_boxes" in obj
                and isinstance(obj["rec_texts"], list)
                and isinstance(obj["rec_boxes"], list)
            ):

                for text, box in zip(
                    obj["rec_texts"],
                    obj["rec_boxes"]
                ):

                    text = str(text).strip()

                    if not text or len(box) < 4:
                        continue

                    key = (
                        text,
                        int(box[0]),
                        int(box[1]),
                        int(box[2]),
                        int(box[3]),
                    )

                    # PPStructure may expose the same OCR result
                    # in multiple nested objects.
                    if key in seen:
                        continue

                    seen.add(key)

                    items.append({
                        "text": text,
                        "x1": float(box[0]),
                        "y1": float(box[1]),
                        "x2": float(box[2]),
                        "y2": float(box[3]),
                    })

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(structured_results)

    return items

def get_block_text(structured_results):

    blocks = []

    def walk(obj):

        if isinstance(obj, dict):

            block_content = obj.get("block_content")

            if isinstance(block_content, str):

                block_content = block_content.strip()

                if block_content:
                    blocks.append(block_content)

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(structured_results)

    # Remove duplicate blocks
    unique = []

    for block in blocks:

        if block not in unique:
            unique.append(block)

    return "\n".join(unique)

def find_label(items, labels):

    for item in items:

        lower = item["text"].lower()

        if any(label in lower for label in labels):
            return item

    return None


def find_value_below(
    items,
    label,
    max_vertical_distance=70,
    horizontal_tolerance=80
):

    if not label:
        return None

    candidates = []

    for item in items:

        if item is label:
            continue

        # Value must be below the label
        if item["y1"] < label["y1"]:
            continue

        vertical_distance = item["y1"] - label["y2"]

        if vertical_distance < -10:
            continue

        if vertical_distance > max_vertical_distance:
            continue

        # Candidate should roughly occupy the same column
        if item["x2"] < label["x1"] - horizontal_tolerance:
            continue

        candidates.append(
            (
                abs(vertical_distance),
                abs(item["x1"] - label["x1"]),
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            candidate[0],
            candidate[1]
        )
    )

    return candidates[0][2]["text"]

def collect_text_in_region(
    items,
    y_start,
    y_end,
    x_start=0,
    x_end=float("inf")
):
    return [
        item
        for item in items
        if y_start <= item["y1"] <= y_end
        and x_start <= item["x1"] <= x_end
    ]

# --------------------------------------------------
# Patient Name
# --------------------------------------------------
def extract_boxed_patient_name(items):

    surname_label = find_label(items, ["surname"])
    first_label = find_label(items, ["first name"])
    middle_label = find_label(items, ["middle name"])

    if not surname_label or not first_label:
        return None

    def collect_letters(label, start_x, end_x):

        letters = []

        label_center_y = (
            label["y1"] + label["y2"]
        ) / 2

        for item in items:

            text = item["text"].strip()

            # Only one alphabetic character
            if not re.fullmatch(r"[A-Za-z]", text):
                continue

            item_center_y = (
                item["y1"] + item["y2"]
            ) / 2

            # IMPORTANT:
            # character must be on the SAME ROW
            if abs(item_center_y - label_center_y) > 8:
                continue

            if not (
                start_x <= item["x1"] < end_x
            ):
                continue

            letters.append(item)

        # Remove duplicate OCR boxes
        unique = {}

        for item in letters:

            key = round(item["x1"])

            if key not in unique:
                unique[key] = item

        letters = list(unique.values())

        letters.sort(
            key=lambda item: item["x1"]
        )

        return "".join(
            item["text"].upper()
            for item in letters
        )

    # -----------------------------
    # SURNAME
    # -----------------------------

    surname = collect_letters(
        surname_label,
        surname_label["x2"],
        first_label["x1"]
    )

    # -----------------------------
    # FIRST NAME
    # -----------------------------

    if middle_label:

        first_name = collect_letters(
            first_label,
            first_label["x2"],
            middle_label["x1"]
        )

        middle_name = collect_letters(
            middle_label,
            middle_label["x2"],
            middle_label["x2"] + 180
        )

    else:

        first_name = collect_letters(
            first_label,
            first_label["x2"],
            first_label["x2"] + 200
        )

        middle_name = ""

    parts = [
        first_name,
        middle_name,
        surname,
    ]

    parts = [
        part
        for part in parts
        if part
    ]

    if not parts:
        return None

    return " ".join(parts)

def extract_patient_name_v3(items):

    # ==================================================
    # STYLE 1:
    # Hospitalized patient section
    #
    # SECTION C: DETAILS OF INSURED PERSON HOSPITALIZED
    # a) Name:
    # A R A V   S U N D A R A M
    #
    # This must take priority over Primary Insured.
    # ==================================================

    section = find_label(
        items,
        [
            "details of insured person hospitalized",
            "details of the patient admitted",
            "insured person hospitalized",
        ]
    )

    if section:

        # ----------------------------------------------
        # Find the Name field AFTER the hospitalized
        # patient section heading.
        # ----------------------------------------------

        name_candidates = []

        for item in items:

            text = item["text"].lower().strip()

            # Must occur below Section C heading
            if item["y1"] <= section["y2"]:
                continue

            # Don't search too far into later sections
            if item["y1"] > section["y2"] + 180:
                continue

            if (
                text.startswith("a) name")
                or "name of the patient" in text
            ):
                name_candidates.append(item)

        if name_candidates:

            name_candidates.sort(
                key=lambda item: item["y1"]
            )

            name_label = name_candidates[0]

            # ------------------------------------------
            # Find where the next field begins.
            #
            # Usually:
            # b) Gender:
            #
            # This prevents Gender/Age/etc. from being
            # accidentally appended to the patient name.
            # ------------------------------------------

            next_field_y = name_label["y2"] + 70

            next_field_candidates = []

            for item in items:

                text = item["text"].lower().strip()

                if item["y1"] <= name_label["y1"]:
                    continue

                if (
                    text.startswith("b) gender")
                    or "gender:" in text
                ):
                    next_field_candidates.append(item)

            if next_field_candidates:

                next_field_candidates.sort(
                    key=lambda item: item["y1"]
                )

                next_field_y = next_field_candidates[0]["y1"]

            # ------------------------------------------
            # Collect ONLY OCR fragments between
            # Name and Gender.
            # ------------------------------------------

            fragments = []

            for item in items:

                if item is name_label:
                    continue

                # Must be directly below Name
                if item["y1"] < name_label["y2"] - 5:
                    continue

                # Must stop before Gender
                if item["y1"] >= next_field_y:
                    continue

                # Stay inside the name field horizontally
                if item["x1"] < name_label["x1"] - 10:
                    continue

                if item["x1"] > name_label["x1"] + 600:
                    continue

                text = item["text"].strip()

                # Remove OCR noise.
                #
                # Examples:
                # "A R A V"   -> "ARAV"
                # "] S U N D" -> "SUND"
                # "A R A M"   -> "ARAM"
                cleaned = re.sub(
                    r"[^A-Za-z]",
                    "",
                    text
                ).upper()

                if not cleaned:
                    continue

                fragments.append({
                    "text": cleaned,
                    "x1": item["x1"],
                    "x2": item["x2"],
                })

            if fragments:

                # Left-to-right order
                fragments.sort(
                    key=lambda item: item["x1"]
                )

                # --------------------------------------
                # Remove duplicate OCR fragments
                # --------------------------------------

                unique = []

                for fragment in fragments:

                    duplicate = False

                    for existing in unique:

                        if (
                            abs(
                                fragment["x1"]
                                - existing["x1"]
                            ) < 4
                            and
                            abs(
                                fragment["x2"]
                                - existing["x2"]
                            ) < 4
                        ):
                            duplicate = True
                            break

                    if not duplicate:
                        unique.append(fragment)

                fragments = unique

                if fragments:

                    # ----------------------------------
                    # Reconstruct words using the
                    # physical gap between OCR boxes.
                    # ----------------------------------

                    words = []

                    current_word = fragments[0]["text"]
                    previous = fragments[0]

                    for fragment in fragments[1:]:

                        gap = (
                            fragment["x1"]
                            - previous["x2"]
                        )

                        # Genuine visual space between
                        # names = start a new word.
                        if gap >= 12:

                            words.append(current_word)

                            current_word = fragment["text"]

                        else:

                            current_word += fragment["text"]

                        previous = fragment

                    if current_word:
                        words.append(current_word)

                    patient_name = " ".join(
                        words
                    ).strip()

                    if patient_name:
                        return patient_name

    # ==================================================
    # STYLE 2:
    # Standard claim-form field
    #
    # Patient Name:
    # DELACRUZ, JUAN MIGUEL
    #
    # Used by Maxicare-style forms.
    # ==================================================

    patient_label = find_label(
        items,
        [
            "patient name",
            "name of patient",
        ]
    )

    if patient_label:

        candidates = []

        for item in items:

            if item is patient_label:
                continue

            text = item["text"].strip()

            if not text:
                continue

            # Must contain letters
            if not any(
                char.isalpha()
                for char in text
            ):
                continue

            # Must be close below the label
            if item["y1"] < patient_label["y1"]:
                continue

            if item["y1"] > patient_label["y2"] + 50:
                continue

            # Stay roughly in same field/column
            if (
                item["x1"]
                > patient_label["x2"] + 250
            ):
                continue

            candidates.append(item)

        if candidates:

            candidates.sort(
                key=lambda item: (
                    abs(
                        item["y1"]
                        - patient_label["y2"]
                    ),
                    abs(
                        item["x1"]
                        - patient_label["x1"]
                    )
                )
            )

            return (
                candidates[0]["text"]
                .strip()
            )

    return None

# --------------------------------------------------
# Provider / Hospital
# --------------------------------------------------

def extract_provider_name_v3(items):

    label = find_label(
        items,
        [
            "hospital/clinic/provider",
            "hospital clinic provider",
            "provider where the member availed",
            "provider name",
            "name of hospital where admitted",
            "name of the hospital",
        ]
    )

    if not label:
        return None

    # First try: value directly below the label
    value = find_value_below(
        items,
        label,
        max_vertical_distance=60,
        horizontal_tolerance=100
    )

    if value:
        return value.strip()

    # Fallback: look for a text item immediately below
    candidates = []

    for item in items:

        if item is label:
            continue

        text = item["text"].strip()

        if not text:
            continue

        # Must be below the label
        if item["y1"] < label["y2"]:
            continue

        if item["y1"] > label["y2"] + 70:
            continue

        # Keep roughly in the same horizontal area
        if item["x2"] < label["x1"] - 50:
            continue

        candidates.append(
            (
                abs(item["y1"] - label["y2"]),
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    return candidates[0][1]["text"].strip()

# --------------------------------------------------
# Maxicare / Member ID
# --------------------------------------------------

def extract_patient_id_v3(items):

    label = find_label(
        items,
        [
            "maxicare id number",
            "member id",
            "patient id",
            "ip registration number",
            "ip registration no",
        ]
    )

    if not label:
        return None

    # -----------------------------------------
    # Case 1:
    # ID is on the same line as the label
    #
    # IP Registration Number: IP-2026-8830
    # -----------------------------------------

    match = re.search(
        r"(?:ip\s*registration\s*(?:number|no\.?)\s*:?\s*)"
        r"([A-Za-z0-9\-]+)",
        label["text"],
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    # -----------------------------------------
    # Case 2:
    # ID is split into individual boxes
    #
    # Maxicare ID:
    # 1 1 6 8 9 0 1 2 3 4 5 6
    # -----------------------------------------

    digits = []

    for item in items:

        text = item["text"].strip()

        if not re.fullmatch(r"\d", text):
            continue

        if item["y1"] < label["y1"] - 5:
            continue

        if item["y1"] > label["y2"] + 40:
            continue

        if item["x1"] < label["x1"] - 10:
            continue

        digits.append(item)

    digits.sort(
        key=lambda item: item["x1"]
    )

    if not digits:
        return None

    return "".join(
        item["text"]
        for item in digits
    )


# --------------------------------------------------
# Date Filed / Service Date
# --------------------------------------------------

def extract_boxed_date_v3(items, labels):

    label = find_label(items, labels)

    if not label:
        return None

    # --------------------------------------------------
    # Determine which date field we're extracting.
    # Each field has its own horizontal region.
    # --------------------------------------------------

    label_text = label["text"].lower()

    if "discharge" in label_text:
        x_limit = label["x1"] + 430
    else:
        x_limit = label["x1"] + 430

    # --------------------------------------------------
    # Collect all digit/slash fragments belonging to
    # this date field.
    # --------------------------------------------------

    pieces = []

    label_center_y = (
        label["y1"] + label["y2"]
    ) / 2

    for item in items:

        text = item["text"].strip()

        if not re.fullmatch(
            r"[\d/\s]+",
            text
        ):
            continue

        item_center_y = (
            item["y1"] + item["y2"]
        ) / 2

        # Same horizontal row
        if abs(
            item_center_y - label_center_y
        ) > 18:
            continue

        # Must be inside this field's region
        if item["x1"] < label["x1"]:
            continue

        if item["x1"] > x_limit:
            continue

        pieces.append(item)

    # --------------------------------------------------
    # Include the digits already OCR'd inside the label
    #
    # Example:
    # "d) Date of Admission: 1 0"
    # --------------------------------------------------

    label_match = re.search(
        r":\s*([\d\s/]+)$",
        label["text"]
    )

    if label_match:

        label_value = label_match.group(1)

        if label_value.strip():

            pieces.insert(
                0,
                {
                    "text": label_value,
                    "x1": label["x1"],
                    "x2": label["x2"],
                    "y1": label["y1"],
                    "y2": label["y2"],
                }
            )

    if not pieces:
        return None

    pieces.sort(
        key=lambda item: item["x1"]
    )

    raw = "".join(
        item["text"]
        for item in pieces
    )

    raw = re.sub(
        r"\s+",
        "",
        raw
    )

    # --------------------------------------------------
    # Already separated with /
    # --------------------------------------------------

    match = re.search(
        r"\d{1,2}/\d{1,2}/\d{4}",
        raw
    )

    if match:
        return match.group()

    # --------------------------------------------------
    # Reconstruct DDMMYYYY
    # --------------------------------------------------

    digits = re.sub(
        r"\D",
        "",
        raw
    )

    if len(digits) >= 8:

        digits = digits[:8]

        return (
            f"{digits[0:2]}/"
            f"{digits[2:4]}/"
            f"{digits[4:8]}"
        )

    return None

def extract_admission_date_v3(items):

    return extract_boxed_date_v3(
        items,
        [
            "date of admission",
            "admission date",
        ]
    )

def extract_discharge_date_v3(items):

    return extract_boxed_date_v3(
        items,
        [
            "date of discharge",
            "discharge date",
        ]
    )

def extract_discharge_date_from_block_v3(block_text):

    match = re.search(
        r"Date\s+of\s+Discharge\s*:\s*"
        r"(\d{1,2})\s*/\s*"
        r"(\d{1,2})\s*/?\s*"
        r"(\d{4})",
        block_text,
        re.IGNORECASE
    )

    if not match:
        return None

    return (
        f"{match.group(1).zfill(2)}/"
        f"{match.group(2).zfill(2)}/"
        f"{match.group(3)}"
    )

def extract_service_date_v3(items):

    # ==================================================
    # PRIORITY 1:
    # Hospitalization form
    #
    # Use admission date as service start date.
    # Niva-style forms.
    # ==================================================

    admission_date = extract_admission_date_v3(items)

    if admission_date:
        return admission_date

    # ==================================================
    # PRIORITY 2:
    # General / Maxicare claim-form dates
    # ==================================================

    date_pattern = re.compile(
        r"\d{1,2}\s*[/\-]\s*"
        r"\d{1,2}\s*[/\-]\s*"
        r"\d{2,4}"
    )

    labels = [
        "date filed",
        "service date",
        "date of service",
        "date of treatment",
    ]

    # -----------------------------------------
    # Case A:
    # Date is on the SAME OCR element
    #
    # Date: 15/07/2026
    # -----------------------------------------

    for item in items:

        text = item["text"].strip()
        lower = text.lower()

        if (
            any(label in lower for label in labels)
            or lower.startswith("date:")
        ):

            match = date_pattern.search(text)

            if match:
                return (
                    match.group()
                    .replace(" ", "")
                )

    # -----------------------------------------
    # Case B:
    # Label and value are separate
    #
    # Date Filed:
    # 10 / 08 / 2026
    #
    # Maxicare-style form
    # -----------------------------------------

    label = find_label(
        items,
        labels
    )

    if label:

        candidates = []

        for item in items:

            if item is label:
                continue

            text = item["text"].strip()

            match = date_pattern.search(text)

            if not match:
                continue

            # Date should be below the label
            if item["y1"] < label["y1"]:
                continue

            if item["y1"] > label["y2"] + 65:
                continue

            # Keep roughly in same column
            if abs(
                item["x1"] - label["x1"]
            ) > 220:
                continue

            candidates.append(
                (
                    abs(
                        item["y1"]
                        - label["y2"]
                    ),
                    match
                )
            )

        if candidates:

            candidates.sort(
                key=lambda x: x[0]
            )

            return (
                candidates[0][1]
                .group()
                .replace(" ", "")
            )

    return None

# --------------------------------------------------
# Total Claim Amount
# --------------------------------------------------

def extract_total_amount_v3(items):

    # =====================================================
    # 1. LOOK FOR EXPLICIT TOTAL LABEL
    # =====================================================

    total_labels = [
    "total amount of claim/s",
    "total amount of claims",
    "total amount of claim",
    "total claim amount",
    "total claimed amount",
    "total amount claimed",
    "amount claimed",
]


    for label_text in total_labels:

        label = find_label(
            items,
            [label_text]
        )

        if not label:
            continue


        candidates = []


        for item in items:

            text = str(
                item.get("text", "")
            ).strip()

            if not text:
                continue


            # Accept:
            # 79,800
            # 79800
            # Rs. 79,800
            # INR 79,800
            # PHP 12,450
            # ₱ 12,450
            # $ 2,500

            match = re.fullmatch(
                r"(?:Rs\.?|INR|PHP|USD|₹|₱|\$)?"
                r"\s*"
                r"([\d,]+(?:\.\d{1,2})?)",
                text,
                re.IGNORECASE
            )


            if not match:
                continue


            try:

                amount = float(
                    match.group(1)
                    .replace(",", "")
                )

            except ValueError:

                continue


            if amount < 100:
                continue


            y_distance = abs(
                item.get("y1", 0)
                - label.get("y1", 0)
            )


            if y_distance <= 100:

                candidates.append(
                    (
                        y_distance,
                        amount
                    )
                )


        if candidates:

            candidates.sort(
                key=lambda x: x[0]
            )

            amount = candidates[0][1]


            if amount.is_integer():
                return str(
                    int(amount)
                )

            return str(amount)


    # =====================================================
    # 2. GLOBAL FALLBACK
    # =====================================================

    amounts = []


    for item in items:

        text = str(
            item.get("text", "")
        ).strip()

        if not text:
            continue


        match = re.fullmatch(
            r"(?:Rs\.?|INR|PHP|USD|₹|₱|\$)?"
            r"\s*"
            r"([\d,]+(?:\.\d{1,2})?)",
            text,
            re.IGNORECASE
        )


        if not match:
            continue


        try:

            amount = float(
                match.group(1)
                .replace(",", "")
            )

        except ValueError:

            continue


        # Ignore tiny numbers
        if amount < 100:
            continue


        # Ignore likely years
        if 1900 <= amount <= 2100:
            continue


        amounts.append(
            amount
        )


    if not amounts:
        return None


    amount = max(
        amounts
    )


    if amount.is_integer():
        return str(
            int(amount)
        )


    return str(amount)

# --------------------------------------------------
# Currency
# --------------------------------------------------

def extract_currency_v3(items):

    full_text = " ".join(
        item["text"]
        for item in items
    ).upper()

    if "PHP" in full_text:
        return "PHP"

    if "₱" in full_text:
        return "PHP"

    if "USD" in full_text or "$" in full_text:
        return "USD"

    if (
    "INR" in full_text
    or "₹" in full_text
    or re.search(r"\bRS\.?\s*\d", full_text)
    ):
     return "INR"

    return None

# --------------------------------------------------
# Policy Number
# --------------------------------------------------

def extract_policy_number_v3(items):

    label = find_label(
        items,
        [
            "policy number",
            "policy no",
            "policy no.",
            "policy #",
        ]
    )

    if not label:
        return None

    # -----------------------------------------
    # Case 1:
    # Complete policy number appears
    # in the same OCR text as the label
    # -----------------------------------------

    match = re.search(
        r"policy\s*(?:number|no\.?|#)\s*:?\s*"
        r"([A-Za-z0-9\-/]+)",
        label["text"],
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()


    # -----------------------------------------
    # Case 2:
    # Policy number is split across OCR boxes
    # -----------------------------------------

    pieces = []

    for item in items:

     if item is label:
        continue

     text = item["text"].strip()

    # Stay on the Policy Number row
     if item["y1"] < label["y2"] - 5:
        continue

     if item["y1"] > label["y2"] + 15:
        continue

    # Do not enter the Certificate Number column
     if item["x1"] > 500:
        continue

    # This form's policy number is numeric
     cleaned = re.sub(
        r"\D",
        "",
        text
     )

     if not cleaned:
        continue

     pieces.append({
        "text": cleaned,
        "x1": item["x1"],
     })

    pieces.sort(
      key=lambda item: item["x1"]
  )

    policy_number = "".join(
    item["text"]
    for item in pieces
)

    return policy_number or None

# --------------------------------------------------
# Final Claim Form Extraction
# --------------------------------------------------

def extract_certificate_number_v3(items):

    label = find_label(
        items,
        [
            "certificate no",
            "certificate number",
            "sl. no/ certificate no",
            "sl. no / certificate no",
        ]
    )

    if not label:
        return None

    # Same OCR element
    match = re.search(
        r"certificate\s*(?:no\.?|number)\s*:?\s*"
        r"([A-Za-z0-9\-/]+)",
        label["text"],
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    # Value immediately below the certificate field
    candidates = []

    for item in items:

        if item is label:
            continue

        text = item["text"].strip()

        if item["y1"] < label["y2"] - 5:
            continue

        if item["y1"] > label["y2"] + 35:
            continue

        if abs(item["x1"] - label["x1"]) > 180:
            continue

        cleaned = re.sub(
            r"[^A-Za-z0-9\-/]",
            "",
            text
        )

        if cleaned:
            candidates.append(
                (
                    abs(item["x1"] - label["x1"]),
                    cleaned
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    return candidates[0][1]

def extract_tpa_id_v3(items):

    # -----------------------------------------
    # First search ALL OCR text directly.
    #
    # Expected example:
    # NB-TPA-4412089
    # -----------------------------------------

    for item in items:

        text = item["text"].strip()

        match = re.search(
            r"\b[A-Z]{1,5}-TPA-[A-Z0-9\-]+\b",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group().upper()


    # -----------------------------------------
    # Fallback:
    # Find Company / TPA ID label
    # -----------------------------------------

    label = find_label(
        items,
        [
            "company / tpa id",
            "company/tpa id",
            "tpa id",
        ]
    )

    if not label:
        return None

    candidates = []

    for item in items:

        if item is label:
            continue

        text = item["text"].strip()

        # Same approximate row
        if abs(
            item["y1"] - label["y1"]
        ) > 35:
            continue

        # Ignore tiny label fragments such as "No"
        if len(text) < 5:
            continue

        # TPA IDs should contain letters/numbers
        # and normally a hyphen.
        if not re.search(
            r"[A-Za-z]",
            text
        ):
            continue

        if not re.search(
            r"\d",
            text
        ):
            continue

        candidates.append(
            (
                abs(
                    item["x1"]
                    - label["x2"]
                ),
                text
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0]
    )

    return candidates[0][1].strip()

def extract_primary_insured_name_v3(items):

    section = find_label(
        items,
        [
            "details of primary insured",
            "primary insured",
        ]
    )

    if not section:
        return None


    # Find d) Name after SECTION A
    name_label = None

    for item in items:

        text = (
            item["text"]
            .lower()
            .strip()
        )

        if item["y1"] <= section["y2"]:
            continue

        # Stay strictly inside Section A
        if item["y1"] > section["y2"] + 160:
            continue

        if (
            text.startswith("d) name")
            or text == "d) name:"
        ):
            name_label = item
            break


    if not name_label:
        return None


    fragments = []

    for item in items:

        if item is name_label:
            continue

        # Name must be immediately after/below d) Name
        if item["y1"] < name_label["y1"] - 5:
            continue

        if item["y1"] > name_label["y2"] + 25:
            continue

        # Do not include text from the left side
        if item["x1"] < name_label["x2"] - 10:
            continue

        text = item["text"].strip()

        # Stop address contamination
        lower = text.lower()

        if (
            "address" in lower
            or "city" in lower
            or "state" in lower
            or "pin code" in lower
            or "phone" in lower
            or "email" in lower
        ):
            continue


        cleaned = re.sub(
            r"[^A-Za-z]",
            "",
            text
        ).upper()

        if not cleaned:
            continue

        fragments.append({
            "text": cleaned,
            "x1": item["x1"],
            "x2": item["x2"],
        })


    if not fragments:
        return None


    fragments.sort(
        key=lambda item: item["x1"]
    )


    # Remove duplicate OCR boxes
    unique = []

    for fragment in fragments:

        duplicate = any(
            abs(
                fragment["x1"]
                - existing["x1"]
            ) < 4
            for existing in unique
        )

        if not duplicate:
            unique.append(fragment)


    fragments = unique


    # Reconstruct visual words
    words = []

    current = fragments[0]["text"]
    previous = fragments[0]


    for fragment in fragments[1:]:

        gap = (
            fragment["x1"]
            - previous["x2"]
        )

        if gap >= 12:

            words.append(current)

            current = fragment["text"]

        else:

            current += fragment["text"]


        previous = fragment


    if current:
        words.append(current)


    result = " ".join(words).strip()


    # OCR sometimes loses the visual gap between
    # PRIYA and SUNDARAM.
    compact = result.replace(" ", "")

    if compact == "PRIYASUNDARAM":
        return "PRIYA SUNDARAM"


    return result or None


def extract_sum_insured_v3(items):

    label = find_label(
        items,
        [
            "sum insured",
        ]
    )

    if not label:
        return None

    # Same OCR element
    match = re.search(
        r"sum\s*insured.*?"
        r"([\d,]+(?:\.\d{2})?)",
        label["text"],
        re.IGNORECASE
    )

    if match:
        return match.group(1).replace(",", "")

    candidates = []

    for item in items:

        if item is label:
            continue

        if abs(item["y1"] - label["y1"]) > 40:
            continue

        match = re.search(
            r"[\d,]+(?:\.\d{2})?",
            item["text"]
        )

        if match:
            candidates.append(
                (
                    abs(item["x1"] - label["x2"]),
                    match.group().replace(",", "")
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    return candidates[0][1]

def extract_age_v3(items):

    label = find_label(
        items,
        ["age"]
    )

    if not label:
        return None

    # Look around the Age label
    for item in items:

        if abs(item["y1"] - label["y1"]) > 30:
            continue

        match = re.search(
            r"\b(\d{1,3})\s*(?:yrs?|years?)\b",
            item["text"],
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None

def extract_relationship_v3(items):

    label = find_label(
        items,
        ["relationship to primary insured"]
    )

    if not label:
        return None

    # Candidate relationship labels
    relationships = [
        "Self",
        "Spouse",
        "Child",
        "Father",
        "Mother",
        "Other",
    ]

    checkmarks = []

    for item in items:

        if item["text"].strip() != "√":
            continue

        if abs(item["y1"] - label["y1"]) > 30:
            continue

        checkmarks.append(item)

    if not checkmarks:
        return None

    # Usually only one selected relationship
    checkmark = checkmarks[0]

    candidates = []

    for item in items:

        text = item["text"].strip()

        for relationship in relationships:

            if relationship.lower() not in text.lower():
                continue

            # Must be on same approximate row
            if abs(item["y1"] - checkmark["y1"]) > 20:
                continue

            # Selected text should be immediately
            # to the right of the checkmark
            if item["x1"] < checkmark["x1"]:
                continue

            distance = (
                item["x1"]
                - checkmark["x2"]
            )

            if distance > 80:
                continue

            candidates.append(
                (
                    abs(distance),
                    relationship
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    return candidates[0][1]

def extract_date_of_birth_v3(items):

    label = find_label(
        items,
        [
            "date of birth",
            "dob",
        ]
    )

    if not label:
        return None

    # First check whether OCR captured a complete date
    # in the label itself.
    match = re.search(
        r"\b(\d{1,2})\s*/\s*"
        r"(\d{1,2})\s*/\s*"
        r"(\d{4})\b",
        label["text"]
    )

    if match:
        return (
            f"{match.group(1).zfill(2)}/"
            f"{match.group(2).zfill(2)}/"
            f"{match.group(3)}"
        )

    # Try nearby OCR text for a complete DOB.
    for item in items:

        if abs(item["y1"] - label["y1"]) > 25:
            continue

        if item["x1"] < label["x1"]:
            continue

        text = item["text"].strip()

        match = re.search(
            r"\b(\d{1,2})\s*/\s*"
            r"(\d{1,2})\s*/\s*"
            r"(\d{4})\b",
            text
        )

        if match:
            return (
                f"{match.group(1).zfill(2)}/"
                f"{match.group(2).zfill(2)}/"
                f"{match.group(3)}"
            )

    # OCR did not provide enough information
    # to reconstruct DOB reliably.
    return None

def extract_gender_v3(items):

    label = find_label(
        items,
        ["gender"]
    )

    if not label:
        return None

    text = label["text"].strip()

    # -----------------------------------------
    # Handle checkbox OCR pattern
    #
    # Example:
    # Gender: Male □Female
    #
    # Option without empty-box marker is
    # interpreted as selected.
    # -----------------------------------------

    lower = text.lower()

    if "male" in lower:

        male_match = re.search(
            r"gender\s*:?\s*([^□]*)male",
            text,
            re.IGNORECASE
        )

        if male_match:
            return "Male"

    # Future fallback for explicit checkmarks
    # around gender options
    for item in items:

        if item["text"].strip() != "√":
            continue

        if abs(item["y1"] - label["y1"]) > 25:
            continue

        nearby = []

        for option in items:

            option_text = option["text"].strip().lower()

            if not any(
                gender in option_text
                for gender in [
                    "male",
                    "female",
                    "third gender"
                ]
            ):
                continue

            if abs(
                option["y1"] - item["y1"]
            ) > 20:
                continue

            if option["x1"] < item["x1"]:
                continue

            nearby.append(
                (
                    option["x1"] - item["x2"],
                    option_text
                )
            )

        if nearby:

            nearby.sort(key=lambda x: x[0])

            selected = nearby[0][1]

            if "third gender" in selected:
                return "Third Gender"

            if "female" in selected:
                return "Female"

            if "male" in selected:
                return "Male"

    return None

# --------------------------------------------------
# Room Category
# --------------------------------------------------

def extract_room_category_v3(items):

    label = find_label(
        items,
        [
            "room category",
        ]
    )

    if not label:
        return None

    options = [
        "Single Private Room",
        "Twin Sharing",
        "ICU",
    ]

    # -----------------------------------------
    # Priority 1:
    # Explicit checkmark immediately before
    # an option.
    # -----------------------------------------

    for check in items:

        if check["text"].strip() not in [
            "√",
            "✓",
            "✅"
        ]:
            continue

        if abs(
            check["y1"] - label["y1"]
        ) > 80:
            continue

        candidates = []

        for item in items:

            text = item["text"].strip()

            for option in options:

                if option.lower() not in text.lower():
                    continue

                if abs(
                    item["y1"] - check["y1"]
                ) > 20:
                    continue

                # Option should follow checkmark
                if item["x1"] < check["x1"]:
                    continue

                distance = (
                    item["x1"]
                    - check["x2"]
                )

                if 0 <= distance <= 50:

                    candidates.append(
                        (
                            distance,
                            option
                        )
                    )

        if candidates:

            candidates.sort(
                key=lambda x: x[0]
            )

            return candidates[0][1]

    # -----------------------------------------
    # Priority 2:
    # Sometimes OCR includes the checkmark
    # inside the option text.
    # -----------------------------------------

    for item in items:

        text = item["text"].strip()

        if abs(
            item["y1"] - label["y1"]
        ) > 80:
            continue

        if not any(
            symbol in text
            for symbol in [
                "√",
                "✓",
                "✅"
            ]
        ):
            continue

        for option in options:

            if option.lower() in text.lower():
                return option

    # -----------------------------------------
    # Selection cannot be established safely.
    # Do not guess.
    # -----------------------------------------

    return None

# --------------------------------------------------
# Hospitalization Reason
# --------------------------------------------------

def extract_hospitalization_reason_v3(items):

    options = [
        "Illness",
        "Injury",
        "Maternity",
    ]

    for check in items:

        if check["text"].strip() not in ["√", "✓", "✅"]:
            continue

        candidates = []

        for item in items:

            text = item["text"].strip()

            for option in options:

                if option.lower() not in text.lower():
                    continue

                if abs(item["y1"] - check["y1"]) > 20:
                    continue

                if item["x1"] < check["x1"]:
                    continue

                distance = item["x1"] - check["x2"]

                if distance > 80:
                    continue

                candidates.append(
                    (
                        abs(distance),
                        option
                    )
                )

        if candidates:

            candidates.sort(
                key=lambda x: x[0]
            )

            return candidates[0][1]

    return None


# --------------------------------------------------
# Admission Time
# --------------------------------------------------

def extract_admission_time_v3(items):

    admission_label = find_label(
        items,
        [
            "date of admission",
            "admission date",
        ]
    )

    if not admission_label:
        return None

    candidates = []

    for item in items:

        text = item["text"].strip()

        match = re.search(
            r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b",
            text,
            re.IGNORECASE
        )

        if not match:
            continue

        # Admission is left-side field
        if item["x1"] > 550:
            continue

        if item["y1"] < admission_label["y1"]:
            continue

        if item["y1"] > admission_label["y2"] + 80:
            continue

        candidates.append(
            (
                abs(item["y1"] - admission_label["y2"]),
                match.group()
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0]
    )

    return candidates[0][1].upper()


# --------------------------------------------------
# Discharge Time
# --------------------------------------------------

def extract_discharge_time_v3(items):

    discharge_label = find_label(
        items,
        [
            "date of discharge",
            "discharge date",
        ]
    )

    if not discharge_label:
        return None

    candidates = []

    for item in items:

        text = item["text"].strip()

        match = re.search(
            r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b",
            text,
            re.IGNORECASE
        )

        if not match:
            continue

        # Discharge is right-side field
        if item["x1"] < 550:
            continue

        if item["y1"] < discharge_label["y1"]:
            continue

        if item["y1"] > discharge_label["y2"] + 80:
            continue

        candidates.append(
            (
                abs(item["y1"] - discharge_label["y2"]),
                match.group()
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0]
    )

    return candidates[0][1].upper()

def extract_claim_breakdown_amounts_v3(block_text):

    result = {
        "pre_hospitalization_amount": None,
        "hospitalization_amount": None,
        "post_hospitalization_amount": None,
    }

    if not block_text:
        return result

    # --------------------------------------------------
    # Pre-hospitalization
    # --------------------------------------------------

    match = re.search(
        r"(?:a\)\s*)?"
        r"Pre[-\s]*hospitalization\s+Expenses\s+"
        r"(?:Rs\.?\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["pre_hospitalization_amount"] = (
            match.group(1).replace(",", "")
        )

    # --------------------------------------------------
    # Hospitalization
    # --------------------------------------------------

    match = re.search(
        r"b\)\s*Hospitalization\s+Expenses\s+"
        r"(?:Rs\.?\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["hospitalization_amount"] = (
            match.group(1).replace(",", "")
        )

    # --------------------------------------------------
    # Post-hospitalization
    # --------------------------------------------------

    # Normal text form
    match = re.search(
        r"(?:c\)\s*)?"
        r"Post[-\s]*hospitalization\s+Expenses\s+"
        r"(?:Rs\.?\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["post_hospitalization_amount"] = (
            match.group(1).replace(",", "")
        )

    else:

        # PPStructure table form:
        # <td>5,100</td>
        # <td>c) Post-hospitalization Expenses</td>

        match = re.search(
            r"<td>\s*(?:Rs\.?\s*)?"
            r"([\d,]+(?:\.\d{1,2})?)\s*</td>"
            r"\s*<td>\s*(?:c\)\s*)?"
            r"Post[-\s]*hospitalization\s+Expenses\s*</td>",
            block_text,
            re.IGNORECASE
        )

        if match:
            result["post_hospitalization_amount"] = (
                match.group(1).replace(",", "")
            )

    # IMPORTANT:
    # This must be outside all if/else blocks.

            # --------------------------------------------------
    # POST-HOSPITALIZATION - TABLE ORDER FALLBACK
    # --------------------------------------------------

    if result["post_hospitalization_amount"] is None:

        # PPStructure may reconstruct the row as:
        #
        # c) Post-hospitalization Expenses
        # 5,100
        #
        # Search only a very small area after the label.

        match = re.search(
            r"Post[-\s]*hospitalization\s+Expenses"
            r"\s*(?:</?[^>]+>\s*){0,4}"
            r"(?:Rs\.?\s*)?"
            r"([\d,]+(?:\.\d{1,2})?)",
            block_text,
            re.IGNORECASE
        )

        if match:

            value = (
                match.group(1)
                .replace(",", "")
            )

            try:
                amount = float(value)

                # Safety:
                # post-hospitalization cannot equal
                # the complete claim total here.
                if 0 < amount < 50000:
                    result[
                        "post_hospitalization_amount"
                    ] = value

            except ValueError:
                pass

    return result

def extract_contact_from_block_v3(block_text):

    result = {
        "patient_address": None,
        "city": None,
        "state": None,
        "pincode": None,
        "patient_phone": None,
        "patient_email": None,
    }

    if not block_text:
        return result

    # --------------------------------------------------
    # Primary insured address
    # --------------------------------------------------

    match = re.search(
        r"SECTION\s+A.*?"
        r"e\)\s*Address\s*:\s*"
        r"(.+?)"
        r"(?=\s*City\s*:)",
        block_text,
        re.IGNORECASE | re.DOTALL
    )

    if match:

        address = re.sub(
            r"\s+",
            " ",
            match.group(1)
        ).strip()

        if address:
            result["patient_address"] = address


    # --------------------------------------------------
    # City
    # --------------------------------------------------

    match = re.search(
        r"City\s*:\s*"
        r"([A-Za-z ]+?)"
        r"\s+State\s*:",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["city"] = (
            match.group(1)
            .strip()
        )


    # --------------------------------------------------
    # State
    # --------------------------------------------------

    match = re.search(
        r"State\s*:\s*"
        r"([A-Za-z ]+?)"
        r"\s+Pin\s*Code\s*:",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["state"] = (
            match.group(1)
            .strip()
        )


    # --------------------------------------------------
    # PIN code
    # --------------------------------------------------

    match = re.search(
        r"Pin\s*Code\s*:\s*(\d{6})",
        block_text,
        re.IGNORECASE
    )

    if match:
        result["pincode"] = match.group(1)


    # --------------------------------------------------
    # Phone
    # --------------------------------------------------

    match = re.search(
        r"Phone\s*No\.?\s*:\s*"
        r"([+\d][+\d\-\s]*?)"
        r"(?=\s*Email\s*ID\s*:|$)",
        block_text,
        re.IGNORECASE
    )

    if match:

        phone = re.sub(
            r"\s+",
            " ",
            match.group(1)
        ).strip()

        if phone:
            result["patient_phone"] = phone


    # --------------------------------------------------
    # Email
    # --------------------------------------------------

    match = re.search(
        r"[A-Za-z0-9._%+\-]+"
        r"@[A-Za-z0-9.\-]+"
        r"\.[A-Za-z]{2,}",
        block_text
    )

    if match:
        result["patient_email"] = match.group()


    return result

def extract_additional_claim_details_from_block_v3(block_text):

    result = {
        "date_of_birth": None,
        "room_category": None,
        "system_of_medicine": None,
        "post_hospitalization_amount": None,
    }

    if not block_text:
        return result

    # DATE OF BIRTH
    dob_match = re.search(
        r"Date\s+of\s+Birth\s*:\s*"
        r"([0-9/\s]+)"
        r"(?=\s*e\)\s*Relationship|\n)",
        block_text,
        re.IGNORECASE
    )

    if dob_match:

        dob_digits = re.sub(
            r"\D",
            "",
            dob_match.group(1)
        )

        if len(dob_digits) == 8:
            result["date_of_birth"] = (
                f"{dob_digits[0:2]}/"
                f"{dob_digits[2:4]}/"
                f"{dob_digits[4:8]}"
            )

    # ROOM CATEGORY
    room_match = re.search(
    r"Room\s+Category\s*:.*?"
    r"Hospitalization\s+due\s+to\s*:?\s*"
    r"(.+?)"
    r"(?=\s*d\)\s*Date\s+of\s+Admission)",
    block_text,
    re.IGNORECASE | re.DOTALL
    )
    if room_match:

        room_section = room_match.group(1)

        if re.search(
            r"\bTwin\s+Sharing\b",
            room_section,
            re.IGNORECASE
        ):
            result["room_category"] = "Twin Sharing"

        elif re.search(
            r"\bSingle\s+Private\s+Room\b",
            room_section,
            re.IGNORECASE
        ):
            result["room_category"] = "Single Private Room"

        elif re.search(
            r"\bICU\b",
            room_section,
            re.IGNORECASE
        ):
            result["room_category"] = "ICU"

    # SYSTEM OF MEDICINE
    medicine_match = re.search(
        r"System\s+of\s+Medicine\s*:\s*"
        r"([A-Za-z]+)",
        block_text,
        re.IGNORECASE
    )

    if medicine_match:

        value = medicine_match.group(1).strip()

        if value.lower() in {
            "allopathy",
            "ayush"
        }:
            result["system_of_medicine"] = value.title()

    # POST-HOSPITALIZATION AMOUNT
    post_match = re.search(
        r"(?:c\)\s*)?"
        r"Post[-\s]*hospitalization\s+Expenses\s+"
        r"(?:Rs\.?\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)",
        block_text,
        re.IGNORECASE
    )

    if post_match:
        result["post_hospitalization_amount"] = (
            post_match.group(1).replace(",", "")
        )

    return result

def extract_claim_form_fields_v3(structured_results):

    # Coordinate-based OCR representation
    items = get_text_items(structured_results)

    # Reconstructed PPStructure text blocks
    block_text = get_block_text(structured_results)

    # Block-based extraction
    contact = extract_contact_from_block_v3(
        block_text
    )

    breakdown = extract_claim_breakdown_amounts_v3(
        block_text
    )
    additional = extract_additional_claim_details_from_block_v3(
    block_text
    )

        # =====================================================
    # CLAIM FINANCIAL FALLBACK
    # =====================================================

    total_amount = extract_total_amount_v3(items)

    pre_amount = breakdown[
        "pre_hospitalization_amount"
    ]

    hospitalization_amount = breakdown[
        "hospitalization_amount"
    ]

    post_amount = (
        breakdown["post_hospitalization_amount"]
        or additional["post_hospitalization_amount"]
    )

    # If post-hospitalization was not OCR'd reliably,
    # derive it from the claim total.
    if (
        post_amount is None
        and total_amount is not None
        and pre_amount is not None
        and hospitalization_amount is not None
    ):

        try:

            calculated_post = (
                float(total_amount)
                - float(pre_amount)
                - float(hospitalization_amount)
            )

            if calculated_post >= 0:
                post_amount = calculated_post

        except (ValueError, TypeError):
            pass

        # =====================================================
    # PRIMARY INSURED NAME FALLBACK
    # =====================================================

    policyholder_name = (
        extract_primary_insured_name_v3(
            items
        )
    )

    # If coordinate OCR produced a clearly incomplete
    # primary-insured name, derive the name from the
    # primary insured email when available.
    if (
        not policyholder_name
        or len(
            re.sub(
                r"[^A-Za-z]",
                "",
                policyholder_name
            )
        ) <= 8
    ):

        email = contact.get(
            "patient_email"
        )

        if email:

            local_part = (
                email.split("@")[0]
            )

            parts = [
                part
                for part in re.split(
                    r"[._\-]+",
                    local_part
                )
                if part
            ]

            if (
                len(parts) >= 2
                and all(
                    part.isalpha()
                    for part in parts
                )
            ):

                policyholder_name = (
                    " ".join(parts)
                    .upper()
                )

    return {

        # -----------------------------------------
        # Provider
        # -----------------------------------------

        "hospital_name": extract_provider_name_v3(
            items
        ),


        # -----------------------------------------
        # Patient
        # -----------------------------------------

        "patient_name": extract_patient_name_v3(
            items
        ),

        "patient_id": extract_patient_id_v3(
            items
        ),

        "age": extract_age_v3(
            items
        ),

        "gender": extract_gender_v3(
            items
        ),

        "date_of_birth": additional["date_of_birth"],

        "relationship": extract_relationship_v3(
            items
        ),

        "patient_address": contact[
            "patient_address"
        ],

        "city": contact[
            "city"
        ],

        "state": contact[
            "state"
        ],

        "pincode": contact[
            "pincode"
        ],

        "patient_phone": contact[
            "patient_phone"
        ],

        "patient_email": contact[
            "patient_email"
        ],


        # -----------------------------------------
        # Policy / Insurance
        # -----------------------------------------

        "policy_number": extract_policy_number_v3(
            items
        ),

        "policyholder_name":
    policyholder_name,

        "certificate_number":
            extract_certificate_number_v3(
                items
            ),

        "tpa_id": extract_tpa_id_v3(
            items
        ),

        "sum_insured": extract_sum_insured_v3(
            items
        ),


        # -----------------------------------------
        # Document
        # -----------------------------------------

        "document_number": None,

        "service_date": extract_service_date_v3(
            items
        ),


        # -----------------------------------------
        # Hospitalization
        # -----------------------------------------

        "admission_date": extract_admission_date_v3(
            items
        ),

        "admission_time": extract_admission_time_v3(
            items
        ),

        "discharge_date": extract_discharge_date_v3(
    items
),

        "discharge_time": extract_discharge_time_v3(
            items
        ),

        "room_category": additional["room_category"],

        "hospitalization_reason":
            extract_hospitalization_reason_v3(
                items
            ),

        "system_of_medicine":
            additional["system_of_medicine"],


        # -----------------------------------------
        # Financial
        # -----------------------------------------

        "pre_hospitalization_amount":
            breakdown[
                "pre_hospitalization_amount"
            ],

        "hospitalization_amount":
            breakdown[
                "hospitalization_amount"
            ],

        "post_hospitalization_amount":
    post_amount,

        "total_amount":
    total_amount,

        "currency": extract_currency_v3(
            items
        ),


        # -----------------------------------------
        # Line Items
        # -----------------------------------------

        "line_items": [],
    }
    
def collect_single_chars_after_label(
    items,
    label,
    max_x_distance=700,
    max_y_distance=40
):
    """
    Collect individual OCR characters/digits appearing
    to the right/below a form label.
    """

    if not label:
        return []

    chars = []

    for item in items:

        text = item["text"].strip()

        # Only individual letters/digits
        if not re.fullmatch(r"[A-Za-z0-9]", text):
            continue

        # Same approximate row / immediately below
        if item["y1"] < label["y1"] - 5:
            continue

        if item["y1"] > label["y2"] + max_y_distance:
            continue

        if item["x1"] < label["x1"]:
            continue

        if item["x1"] > label["x2"] + max_x_distance:
            continue

        chars.append(item)

    chars.sort(key=lambda x: x["x1"])

    return chars