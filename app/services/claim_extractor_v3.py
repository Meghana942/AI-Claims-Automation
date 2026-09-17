import re


def get_all_text(structured_results):
    """
    Collect OCR text from PPStructureV3 output.
    """

    texts = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():

                if key == "rec_texts" and isinstance(value, list):
                    texts.extend(
                        str(item).strip()
                        for item in value
                        if str(item).strip()
                    )

                else:
                    walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(structured_results)

    return texts

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

    unique_blocks = []

    for block in blocks:

        if block not in unique_blocks:
            unique_blocks.append(block)

    return "\n".join(unique_blocks)

def clean_html_value(value):

    if not value:
        return None

    value = re.sub(
        r"<[^>]+>",
        "",
        str(value)
    )

    value = value.strip()

    value = re.sub(
        r"^[\s:·]+",
        "",
        value
    )

    return value or None

def extract_block_value(block_text, label_patterns):

    if not block_text:
        return None

    for label_pattern in label_patterns:

        match = re.search(
            rf"{label_pattern}\s*</td>"
            rf"\s*<td[^>]*>\s*:?\s*</td>"
            rf"\s*<td[^>]*>\s*:?\s*([^<]+?)\s*</td>",
            block_text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value:
                return value

    return None

def extract_amount_after_label_v3(
    structured_results,
    labels,
    lookahead=4
):

    texts = get_all_text(
        structured_results
    )

    for i, text in enumerate(texts):

        normalized = re.sub(
            r"[^a-z]",
            "",
            text.lower()
        )

        matched = False

        for label in labels:

            normalized_label = re.sub(
                r"[^a-z]",
                "",
                label.lower()
            )

            if normalized_label in normalized:
                matched = True
                break

        if not matched:
            continue

        # Check label itself and following OCR items
        candidates = [
            text,
            *texts[i + 1:i + 1 + lookahead]
        ]

        for candidate in candidates:

            match = re.search(
                r"-?\s*[\d,]+\.\d{2}",
                candidate
            )

            if not match:
                continue

            value = (
                match.group()
                .replace(",", "")
                .replace(" ", "")
            )

            try:
                return abs(float(value))

            except ValueError:
                continue

    return None

def extract_invoice_summary_amount_v3(
    structured_results
):

    texts = get_all_text(
        structured_results
    )

    result = {
        "subtotal": None,
        "discount": None,
    }

    for i, text in enumerate(texts):

        normalized = re.sub(
            r"[^a-z]",
            "",
            text.lower()
        )

        # -----------------------------------------
        # SUBTOTAL
        # -----------------------------------------

        if normalized in {
            "subtotal",
            "subtotalamount",
        }:

            for candidate in texts[i + 1:i + 4]:

                match = re.search(
                    r"[\d,]+\.\d{2}",
                    candidate
                )

                if match:

                    result["subtotal"] = (
                        match.group()
                        .replace(",", "")
                    )

                    break


        # -----------------------------------------
        # DISCOUNT
        # -----------------------------------------

        if normalized == "discount":

            for candidate in texts[i + 1:i + 4]:

                match = re.search(
                    r"-?\s*[\d,]+\.\d{2}",
                    candidate
                )

                if match:

                    result["discount"] = (
                        match.group()
                        .replace(",", "")
                        .replace(" ", "")
                        .lstrip("-")
                    )

                    break

    return result

def extract_rich_invoice_details_v3(structured_results):
    """
    Extract richer invoice fields from PPStructure output.

    Supports:
    - HTML table layouts
    - Plain-text clinical/hospitalization blocks
    - Invoice 1 and Invoice 2 variations

    Missing fields remain None.
    """

    block_text = get_block_text(structured_results)
    texts = get_all_text(structured_results)

    summary = extract_invoice_summary_amount_v3(
        structured_results
    )

    result = {
        # Patient / policy
        "patient_name": None,
        "patient_id": None,
        "age": None,
        "gender": None,
        "member_id": None,
        "policy_number": None,
        "policyholder_name": None,
        "relationship": None,
        "insurer_name": None,
        "tpa_name": None,

        # Provider
        "hospital_address": None,
        "hospital_phone": None,
        "hospital_email": None,
        "hospital_gstin": None,

        # Hospitalization
        "admission_number": None,
        "admission_date": None,
        "admission_time": None,
        "discharge_date": None,
        "discharge_time": None,
        "room_category": None,

        # Clinical
        "doctor_name": None,
        "specialization": None,
        "diagnosis": None,
        "procedure": None,

        # Financial
        "subtotal": summary.get("subtotal"),
        "discount": summary.get("discount"),
        "tax_amount": None,
        "amount_approved": None,
        "copay_amount": None,
        "amount_paid": None,

        # Payment
        "payment_method": None,
        "transaction_id": None,
        "payment_date": None,
    }

    if not block_text:
        return result

    # ==================================================
    # LOCAL HELPERS
    # ==================================================

    def html_value(labels):
        """
        Extract value from common two-column HTML layout:

        <td>Label</td>
        <td>Value</td>
        """

        for label in labels:

            match = re.search(
                rf"<td[^>]*>\s*{label}\s*:?\s*</td>"
                rf"\s*<td[^>]*>\s*:?\s*([^<]+?)\s*</td>",
                block_text,
                re.IGNORECASE,
            )

            if not match:
                continue

            value = clean_html_value(
                match.group(1)
            )

            if value:
                return (
                    value
                    .rstrip(":")
                    .strip()
                )

        return None


    def html_value_three_column(labels):
        """
        Extract value from three-column layout:

        <td>Label</td>
        <td>:</td>
        <td>Value</td>
        """

        for label in labels:

            match = re.search(
                rf"<td[^>]*>\s*{label}\s*</td>"
                rf"\s*<td[^>]*>\s*:?\s*</td>"
                rf"\s*<td[^>]*>\s*:?\s*([^<]+?)\s*</td>",
                block_text,
                re.IGNORECASE,
            )

            if not match:
                continue

            value = clean_html_value(
                match.group(1)
            )

            if value:
                return (
                    value
                    .rstrip(":")
                    .strip()
                )

        return None


    def flexible_html_value(labels):
        """
        Try the normal two-column layout first,
        then the Invoice 1 three-column layout.
        """

        value = html_value(labels)

        if value and value != ":":
            return value

        value = html_value_three_column(
            labels
        )

        if value and value != ":":
            return value

        return None


    def plain_value(
        source_text,
        label,
        stop_labels
    ):
        """
        Extract a value from a plain-text block using
        the next known label as the stopping point.
        """

        if not source_text:
            return None

        if stop_labels:

            stop_pattern = "|".join(
                re.escape(item)
                for item in stop_labels
            )

            pattern = (
                rf"{re.escape(label)}\s*:?\s*"
                rf"(.*?)"
                rf"(?=\s*(?:{stop_pattern})\s*:?\s*|$)"
            )

        else:

            pattern = (
                rf"{re.escape(label)}\s*:?\s*"
                rf"(.*?)$"
            )

        match = re.search(
            pattern,
            source_text,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return None

        value = re.sub(
            r"\s+",
            " ",
            match.group(1)
        ).strip()

        return value or None


    def amount_after(label_pattern):
        """
        Extract a financial amount following a label.
        HTML table is preferred, with plain-text fallback.
        """

        value = html_value(
            [label_pattern]
        )

        if value:

            match = re.search(
                r"-?\s*[\d,]+\.\d{2}",
                value
            )

            if match:

                return (
                    match.group()
                    .replace(",", "")
                    .replace(" ", "")
                    .lstrip("-")
                )

        match = re.search(
            rf"{label_pattern}"
            rf".{{0,160}}?"
            rf"(-?\s*[\d,]+\.\d{{2}})",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            return (
                match.group(1)
                .replace(",", "")
                .replace(" ", "")
                .lstrip("-")
            )

        return None


    # ==================================================
    # PATIENT DETAILS
    # ==================================================

    # Supports:
    #
    # Invoice 2:
    # Patient Name : | Mr. Vikram Reddy
    #
    # Invoice 1:
    # Patient Name | : | Mrs. Kavya Iyer

    result["patient_name"] = (
        flexible_html_value(
            [
                r"Patient\s+Name",
            ]
        )
    )


    # --------------------------------------------------
    # Patient ID / UHID
    # --------------------------------------------------

    result["patient_id"] = (
        flexible_html_value(
            [
                r"Patient\s+ID\s*/?\s*UHID",
                r"Patient\s+ID",
                r"UHID",
            ]
        )
    )


    # --------------------------------------------------
    # Patient ID / UHID fallback from OCR text
    # --------------------------------------------------

    if (
    not result["patient_id"]
    or re.fullmatch(
        r"\+?\d{10,13}",
        result["patient_id"]
    )
):

     result["patient_id"] = None

     for i, text in enumerate(texts):

        normalized = re.sub(
            r"\s+",
            " ",
            str(text)
        ).strip()

        if not re.search(
            r"patient\s*id\s*/?\s*uhid|\buhid\b",
            normalized,
            re.IGNORECASE
        ):
            continue

        # First try value in the same OCR text
        match = re.search(
            r"(?:patient\s*id\s*/?\s*uhid|\buhid\b)"
            r"\s*:?\s*"
            r"([A-Za-z][A-Za-z0-9/\-]{5,})",
            normalized,
            re.IGNORECASE
        )

        if match:

            candidate = match.group(1).strip()

            if not candidate.startswith("+"):
                result["patient_id"] = candidate
                break

        # Otherwise inspect nearby OCR items
        for candidate in texts[i + 1:i + 6]:

            candidate = str(candidate).strip()

            # Ignore punctuation
            if not candidate:
                continue

            if candidate in {
                ":",
                "·",
                "-",
            }:
                continue

            # Never allow a phone number to become patient ID
            if re.fullmatch(
                r"\+?\d{10,13}",
                candidate
            ):
                continue

            # Patient/UHID-style identifier
            if re.fullmatch(
                r"[A-Za-z][A-Za-z0-9/\-]{5,}",
                candidate
            ):
                result["patient_id"] = candidate
                break

        if result["patient_id"]:
            break


    # --------------------------------------------------
    # Age / Gender
    # --------------------------------------------------

    age_gender = flexible_html_value(
        [
            r"Age\s*/\s*Gender",
        ]
    )

    match = None

    if age_gender:

        match = re.search(
            r"(\d{1,3})\s*Y?\s*/\s*"
            r"(Male|Female|Other)",
            age_gender,
            re.IGNORECASE,
        )

    if not match:

        match = re.search(
            r"Age\s*/\s*Gender"
            r".{0,100}?"
            r"(\d{1,3})\s*Y?\s*/\s*"
            r"(Male|Female|Other)",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

    if match:

        result["age"] = (
            match.group(1)
        )

        result["gender"] = (
            match.group(2)
            .title()
        )


    # ==================================================
    # POLICY / INSURANCE
    # ==================================================

    result["policyholder_name"] = (
        flexible_html_value(
            [
                r"Policyholder\s+Name",
            ]
        )
    )

        # ==================================================
    # POLICYHOLDER NAME OCR FALLBACK
    # ==================================================

    if not result["policyholder_name"]:

        for i, text in enumerate(texts):

            normalized = re.sub(
                r"[^a-z]",
                "",
                str(text).lower()
            )

            if "policyholdername" not in normalized:
                continue


            # Same OCR item:
            # Policyholder Name: Mr. R. Iyer
            match = re.search(
                r"policyholder\s*name\s*:?\s*(.+)",
                str(text),
                re.IGNORECASE
            )

            if match:

                candidate = (
                    match.group(1).strip()
                )

                if candidate:

                    result["policyholder_name"] = (
                        candidate
                    )

                    break


            # Otherwise inspect nearby OCR values
            for candidate in texts[i + 1:i + 6]:

                candidate = (
                    str(candidate).strip()
                )

                if not candidate:
                    continue

                candidate_lower = (
                    candidate.lower()
                )

                # Skip labels
                if any(
                    label in candidate_lower
                    for label in (
                        "member id",
                        "policy no",
                        "policy number",
                        "relationship",
                        "insurer",
                        "tpa",
                    )
                ):
                    continue

                # Name-shaped value
                if re.fullmatch(
                    r"(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?"
                    r"\s*"
                    r"[A-Za-z]"
                    r"[A-Za-z.\- ]{1,50}",
                    candidate
                ):

                    result["policyholder_name"] = (
                        candidate
                    )

                    break


            if result["policyholder_name"]:
                break

    result["relationship"] = (
        flexible_html_value(
            [
                r"Relationship",
            ]
        )
    )

    if result["relationship"]:

        result["relationship"] = (
            result["relationship"]
            .title()
        )


    # --------------------------------------------------
    # Policy Number
    # --------------------------------------------------

    result["policy_number"] = (
        flexible_html_value(
            [
                r"Policy\s+No\.?",
                r"Policy\s+Number",
            ]
        )
    )

    if result["policy_number"]:

        result["policy_number"] = (
            result["policy_number"]
            .rstrip(":")
            .strip()
        )


    # Generic fallback for policy-number styles
    if not result["policy_number"]:

        match = re.search(
            r"\b"
            r"(?:"
            r"BAJAJ/HLT/[A-Za-z0-9\-/]+"
            r"|"
            r"HDF/[A-Za-z0-9\-/]+"
            r")"
            r"\b",
            block_text,
            re.IGNORECASE,
        )

        if match:

            result["policy_number"] = (
                match.group(0)
                .strip()
            )


    # --------------------------------------------------
    # Member ID
    # --------------------------------------------------

    result["member_id"] = (
        flexible_html_value(
            [
                r"Member\s*ID",
            ]
        )
    )

    if not result["member_id"]:

        match = re.search(
            r"\b"
            r"(?:BAJMEM|HDFMEM)"
            r"[A-Za-z0-9\-]+"
            r"\b",
            block_text,
            re.IGNORECASE,
        )

        if match:

            result["member_id"] = (
                match.group(0)
                .strip()
            )


    # --------------------------------------------------
    # Insurer
    # --------------------------------------------------

    result["insurer_name"] = (
        flexible_html_value(
            [
                r"Insurer\s+Name",
                r"Insurer",
            ]
        )
    )


    # --------------------------------------------------
    # TPA
    # --------------------------------------------------

    result["tpa_name"] = (
        flexible_html_value(
            [
                r"TPA\s+Name",
                r"TPA",
            ]
        )
    )


    # ==================================================
    # PROVIDER DETAILS
    # ==================================================

    for text in texts:

        text = str(text).strip()

        # Phone
        if not result["hospital_phone"]:

            match = re.search(
                r"\+91\d{10}",
                text
            )

            if match:

                result["hospital_phone"] = (
                    match.group(0)
                )

        # Email
        if not result["hospital_email"]:

            match = re.search(
                r"[A-Za-z]"
                r"[A-Za-z0-9._%+\-]*"
                r"@[A-Za-z0-9.\-]+"
                r"\.[A-Za-z]{2,}",
                text
            )

            if match:

                result["hospital_email"] = (
                    match.group(0)
                )


    # --------------------------------------------------
    # GSTIN
    # --------------------------------------------------

    match = re.search(
        r"GSTIN\s*:\s*([A-Z0-9]+)",
        block_text,
        re.IGNORECASE,
    )

    if match:

        result["hospital_gstin"] = (
            match.group(1)
        )


    # --------------------------------------------------
    # Hospital Address
    # --------------------------------------------------

    # Generic address extraction:
    # find a block containing hospital + India,
    # then capture from "No." through "India".

    for block in block_text.split("\n"):

        block = block.strip()

        if not block:
            continue

        lower = block.lower()

        if (
            "hospital" not in lower
            or "india" not in lower
        ):
            continue

        match = re.search(
            r"(No\.\s*.*?India)",
            block,
            re.IGNORECASE,
        )

        if match:

            result["hospital_address"] = (
                re.sub(
                    r"\s+",
                    " ",
                    match.group(1)
                )
                .strip()
            )

            break


    # ==================================================
    # HOSPITALIZATION / CLINICAL
    # ==================================================

    # First try HTML layouts.

    result["admission_number"] = (
        flexible_html_value(
            [
                r"Admission\s+No\.?",
                r"Admission\s+Number",
            ]
        )
    )

    result["room_category"] = (
        flexible_html_value(
            [
                r"Room\s+Category",
                r"Bed\s+Category",
            ]
        )
    )

    result["doctor_name"] = (
        flexible_html_value(
            [
                r"Attending\s+Doctor",
                r"Doctor\s+Name",
            ]
        )
    )

    result["specialization"] = (
        flexible_html_value(
            [
                r"Department",
                r"Specialization",
            ]
        )
    )

    result["diagnosis"] = (
        flexible_html_value(
            [
                r"Diagnosis\s*\(ICD-10\)",
                r"Diagnosis",
            ]
        )
    )

    result["procedure"] = (
        flexible_html_value(
            [
                r"Procedure\s+Performed",
                r"Procedure",
            ]
        )
    )


    # --------------------------------------------------
    # Locate plain clinical block
    # --------------------------------------------------

    clinical_block = None

    for block in block_text.split("\n"):

        block = block.strip()

        if not block:
            continue

        if (
            "admission" in block.lower()
            and "discharge" in block.lower()
        ):

            clinical_block = block
            break

    if not clinical_block:
        clinical_block = block_text


    # --------------------------------------------------
    # Admission Number fallback
    # --------------------------------------------------

    if not result["admission_number"]:

        match = re.search(
            r"Admission\s+No\.?\s*:?\s*"
            r"(.*?)"
            r"(?=\s*Admission\s+Date)",
            clinical_block,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            result["admission_number"] = (
                re.sub(
                    r"\s+",
                    "",
                    match.group(1)
                )
                .lstrip(":")
                .strip()
            )


    # --------------------------------------------------
    # Admission / Discharge dates + times
    # --------------------------------------------------

    date_pattern = (
        r"\d{1,2}\s*[-/]\s*"
        r"[A-Za-z]{3,9}\s*[-/]\s*"
        r"\d{4}"
        r"|"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{4}"
    )


    match = re.search(
        rf"Admission\s+Date\s*&\s*Time"
        rf"\s*:?\s*"
        rf"({date_pattern})"
        rf"\s*"
        rf"(\d{{1,2}}:\d{{2}}\s*(?:AM|PM))?",
        clinical_block,
        re.IGNORECASE,
    )

    if match:

        result["admission_date"] = (
            match.group(1)
            .strip()
        )

        if match.group(2):

            result["admission_time"] = (
                re.sub(
                    r"\s+",
                    "",
                    match.group(2).upper()
                )
            )


    match = re.search(
        rf"Discharge\s+Date\s*&\s*Time"
        rf"\s*:?\s*"
        rf"({date_pattern})"
        rf"\s*"
        rf"(\d{{1,2}}:\d{{2}}\s*(?:AM|PM))?",
        clinical_block,
        re.IGNORECASE,
    )

    if match:

        result["discharge_date"] = (
            match.group(1)
            .strip()
        )

        if match.group(2):

            result["discharge_time"] = (
                re.sub(
                    r"\s+",
                    " ",
                    match.group(2).upper()
                )
                .strip()
            )


    # --------------------------------------------------
    # Room / Bed Category fallback
    # --------------------------------------------------

    if not result["room_category"]:

        result["room_category"] = (
            plain_value(
                clinical_block,
                "Bed Category",
                [
                    "Attending Doctor",
                    "Specialization",
                    "Diagnosis",
                    "Procedure Performed",
                    "Corporate Name",
                ]
            )
        )


    # --------------------------------------------------
    # Doctor fallback
    # --------------------------------------------------

    if not result["doctor_name"]:

        result["doctor_name"] = (
            plain_value(
                clinical_block,
                "Attending Doctor",
                [
                    "Specialization",
                    "Diagnosis",
                    "Procedure Performed",
                    "Corporate Name",
                ]
            )
        )


    # --------------------------------------------------
    # Specialization fallback
    # --------------------------------------------------

    if not result["specialization"]:

        result["specialization"] = (
            plain_value(
                clinical_block,
                "Specialization",
                [
                    "Diagnosis",
                    "Procedure Performed",
                    "Corporate Name",
                ]
            )
        )


    # --------------------------------------------------
    # Diagnosis fallback
    # --------------------------------------------------

    if not result["diagnosis"]:

        result["diagnosis"] = (
            plain_value(
                clinical_block,
                "Diagnosis (ICD-10)",
                [
                    "Procedure Performed",
                    "Corporate Name",
                ]
            )
        )


    # --------------------------------------------------
    # Procedure fallback
    # --------------------------------------------------

    if not result["procedure"]:

        result["procedure"] = (
            plain_value(
                clinical_block,
                "Procedure Performed",
                [
                    "Corporate Name",
                ]
            )
        )


    # --------------------------------------------------
    # Invoice 1 date fallback
    #
    # Invoice 1 sometimes has date/time split across
    # reconstructed HTML/OCR items.
    # --------------------------------------------------

    if not result["admission_date"]:

        match = re.search(
            rf"Admission\s+Date\s*&\s*Time"
            rf".{{0,100}}?"
            rf"({date_pattern})",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            result["admission_date"] = (
                match.group(1)
                .strip()
            )


    if not result["discharge_date"]:

        match = re.search(
            rf"Discharge\s+Date\s*&\s*Time"
            rf".{{0,100}}?"
            rf"({date_pattern})",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            result["discharge_date"] = (
                match.group(1)
                .strip()
            )


    if not result["admission_time"]:

        match = re.search(
            r"Admission\s+Date\s*&\s*Time"
            r".{0,150}?"
            r"(\d{1,2}:\d{2}\s*(?:AM|PM))",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            result["admission_time"] = (
                match.group(1)
                .upper()
            )


    if not result["discharge_time"]:

        match = re.search(
            r"Discharge\s+Date\s*&\s*Time"
            r".{0,150}?"
            r"(\d{1,2}:\d{2}\s*(?:AM|PM))",
            block_text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:

            result["discharge_time"] = (
                match.group(1)
                .upper()
            )


    # ==================================================
    # FINANCIAL DETAILS
    # ==================================================

    if not result["subtotal"]:

        result["subtotal"] = (
            amount_after(
                r"Sub\s*Total"
            )
        )


    if not result["discount"]:

        result["discount"] = (
            amount_after(
                r"(?:Less\s*:\s*)?"
                r"(?:Package\s+)?"
                r"Discount"
            )
        )

        # ==================================================
    # TAX AMOUNT
    # ==================================================
    #
    # Priority:
    # 1. Explicit "Total Tax"
    # 2. Explicit "Tax Amount"
    # 3. CGST + SGST + IGST
    # ==================================================

    result["tax_amount"] = (
        extract_amount_after_label_v3(
            structured_results,
            [
                "Total Tax",
                "Tax Amount",
            ],
            lookahead=4
        )
    )


    # --------------------------------------------------
    # GST COMPONENT FALLBACK
    # --------------------------------------------------

    if result["tax_amount"] is None:

        cgst = extract_amount_after_label_v3(
            structured_results,
            [
                "CGST",
            ],
            lookahead=3
        )

        sgst = extract_amount_after_label_v3(
            structured_results,
            [
                "SGST",
            ],
            lookahead=3
        )

        igst = extract_amount_after_label_v3(
            structured_results,
            [
                "IGST",
            ],
            lookahead=3
        )


        gst_components = [
            value
            for value in (
                cgst,
                sgst,
                igst
            )
            if value is not None
        ]


        if gst_components:

            result["tax_amount"] = sum(
                gst_components
            )

    result["amount_approved"] = (
        amount_after(
            r"Amount\s+Approved\s+by\s+Insurer"
        )
    )


    result["copay_amount"] = (
        amount_after(
            r"Patient\s+Payable"
            r"\s*/\s*"
            r"Co-pay"
            r"(?:\s*/\s*Non\s+Payable)?"
        )
    )


    result["amount_paid"] = (
        amount_after(
            r"Amount\s+Paid"
        )
    )


    # ==================================================
    # PAYMENT DETAILS
    # ==================================================

    result["payment_method"] = (
        flexible_html_value(
            [
                r"Payment\s+Mode",
                r"Payment\s+Method",
            ]
        )
    )

        # ==================================================
    # PAYMENT DATE FALLBACK / VALIDATION
    # ==================================================

    date_value_pattern = (
        r"\d{1,2}\s*[-/]\s*"
        r"[A-Za-z]{3,9}\s*[-/]\s*"
        r"\d{4}"
        r"|"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{4}"
    )

    # Reject values that are clearly another label
    if (
        result["payment_date"]
        and not re.search(
            date_value_pattern,
            result["payment_date"],
            re.IGNORECASE
        )
    ):
        result["payment_date"] = None


    # Search OCR text around "Payment Date"
    if not result["payment_date"]:

        for i, text in enumerate(texts):

            normalized = re.sub(
                r"[^a-z]",
                "",
                str(text).lower()
            )

            if "paymentdate" not in normalized:
                continue


            # Same OCR item first
            match = re.search(
                date_value_pattern,
                str(text),
                re.IGNORECASE
            )

            if match:

                result["payment_date"] = (
                    match.group().strip()
                )

                break


            # Then nearby OCR items
            for candidate in texts[i + 1:i + 6]:

                match = re.search(
                    date_value_pattern,
                    str(candidate),
                    re.IGNORECASE
                )

                if match:

                    result["payment_date"] = (
                        match.group().strip()
                    )

                    break


            if result["payment_date"]:
                break

    result["transaction_id"] = (
        flexible_html_value(
            [
                r"UPI\s*/\s*Transaction\s+ID",
                r"Transaction\s+ID",
                r"Transaction\s+No\.?",
            ]
        )
    )


    result["payment_date"] = (
        flexible_html_value(
            [
                r"Payment\s+Date",
            ]
        )
    )


    return result

def extract_patient_name_v3(structured_results):

    texts = get_all_text(structured_results)

    # =====================================================
    # CASE 1 — Explicit "Name: John Doe"
    # =====================================================

    for text in texts:

        text = str(text).strip()

        match = re.search(
            r"^name\s*:\s*(.+)$",
            text,
            re.IGNORECASE
        )

        if match:

            candidate = match.group(1).strip()

            if candidate:
                return candidate


    # =====================================================
    # CASE 2 — Explicit "Patient Name: Neha K"
    # =====================================================

    for text in texts:

        text = str(text).strip()

        match = re.search(
            r"patient\s*name\s*:?\s*(.+)",
            text,
            re.IGNORECASE
        )

        if match:

            candidate = match.group(1).strip()

            if candidate:
                return candidate


    # =====================================================
    # CASE 3 — PATIENT DETAILS section
    #
    # Handles Apollo layout:
    #
    # PATIENT DETAILS
    # Neha K
    # D group layout...
    # =====================================================

    section_labels = [
        "patient details",
        "patient information",
        "patientinformation",
        "bill to",
    ]

    skip_words = [
        "patient id",
        "patient code",
        "ip no",
        "id no",
        "uhid",
        "mrn",
        "bill no",
        "bill number",
        "invoice no",
        "invoice number",
        "receipt no",
        "receipt number",
        "address",
        "phone",
        "email",
        "date of birth",
        "dob",
        "payment",
        "service date",
        "admission",
        "discharge",
        "inpatient bill",
    ]


    for i, text in enumerate(texts):

        text = str(text).strip()

        normalized_section = re.sub(
            r"[^a-z]",
            "",
            text.lower()
        )

        is_patient_section = any(
            re.sub(
                r"[^a-z]",
                "",
                label.lower()
            ) in normalized_section
            for label in section_labels
        )

        if not is_patient_section:
            continue


        # Search a limited area immediately after
        # the patient-details heading.
        for candidate in texts[i + 1:i + 12]:

            candidate = str(candidate).strip()

            if not candidate:
                continue


            candidate_lower = candidate.lower()


            # ---------------------------------------------
            # Explicit Name: value
            # ---------------------------------------------

            match = re.search(
                r"(?:patient\s*)?name\s*:?\s*(.+)",
                candidate,
                re.IGNORECASE
            )

            if match:

                value = match.group(1).strip()

                if value:
                    return value


            # ---------------------------------------------
            # Reject labels / metadata
            # ---------------------------------------------

            if any(
                word in candidate_lower
                for word in skip_words
            ):
                continue


            # Reject obvious IDs/numbers
            if re.fullmatch(
                r"[\d\s:/\-]+",
                candidate
            ):
                continue


            # Reject addresses beginning with numbers
            if re.match(
                r"^\d+\s",
                candidate
            ):
                continue


            # Reject long address-looking strings
            if any(
                word in candidate_lower
                for word in (
                    "street",
                    "road",
                    "layout",
                    "nagar",
                    "bangalore",
                    "bengaluru",
                    "city",
                    "state",
                    "zip",
                    "avenue",
                )
            ):
                continue


            # Must contain letters
            if not re.search(
                r"[A-Za-z]",
                candidate
            ):
                continue


            # ---------------------------------------------
            # Name-shaped candidate
            #
            # Allows:
            # Neha K
            # John Doe
            # Mrs. Kavya Iyer
            # Mr. Vikram Reddy
            # ---------------------------------------------

            words = candidate.split()

            if 1 <= len(words) <= 6:

                if all(
                    re.fullmatch(
                        r"[A-Za-z.'\-]+",
                        word
                    )
                    for word in words
                ):
                    return candidate


    return None

def extract_document_number_v3(structured_results):
    texts = get_all_text(structured_results)
    block_text = get_block_text(structured_results)

    # Prefer structured invoice/receipt tables.
    match = re.search(
        r"<td[^>]*>\s*(?:Tax\s+)?Invoice\s+No\.?\s*</td>\s*"
        r"<td[^>]*>\s*:?[\s]*([^<]+)\s*</td>",
        block_text,
        re.IGNORECASE,
    )
    if match:
        return clean_html_value(match.group(1))

    for text in texts:
        match = re.search(r"receipt\s*number\s*:\s*([A-Za-z0-9\-/]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    labels = [
        "tax invoice no",
        "invoice no",
        "invoice number",
        "bill no",
        "bill number",
        "receipt no",
        "receipt number",
        "receiptnumber",
    ]

    for i, text in enumerate(texts):
        lower = text.lower()
        if any(label in lower for label in labels):
            parts = re.split(r":", text, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip().lstrip(":").strip()
            if i + 1 < len(texts):
                return texts[i + 1].strip().lstrip(":").strip()

    return None

def extract_rich_receipt_details_v3(structured_results):
    """
    Extract rich fields from receipt-style medical documents.

    Handles OCR-collapsed labels such as:
        HospitalAddress:
        DateofBirth:
        TotalCharges:
        PaymentMethod:
        TransactionID:

    Missing values remain None.
    """

    texts = get_all_text(
        structured_results
    )

    block_text = get_block_text(
        structured_results
    )

    result = {
        "hospital_address": None,
        "hospital_phone": None,
        "patient_phone": None,
"patient_email": None,
"tax_amount": None,

        "date_of_birth": None,
        "patient_address": None,

        "document_date": None,

        "total_amount": None,
        "amount_paid": None,

        "payment_method": None,
        "transaction_id": None,
        "payment_date": None,
    }


    # ==================================================
    # HELPER
    # ==================================================

    def clean_collapsed_text(value):

        if not value:
            return None

        value = str(value).strip()

        return value or None


    # ==================================================
    # WORK DIRECTLY FROM rec_texts
    # ==================================================

    for text in texts:

        text = str(text).strip()

        if not text:
            continue

        normalized = (
            text
            .lower()
            .replace(" ", "")
        )


        # --------------------------------------------------
        # Hospital Address
        #
        # OCR:
        # HospitalAddress:123HealthAvenueMetropolisState...
        # --------------------------------------------------

        if normalized.startswith(
            "hospitaladdress:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            if value:

                result[
                    "hospital_address"
                ] = clean_collapsed_text(
                    value
                )

            continue


        # --------------------------------------------------
        # Hospital Phone
        #
        # OCR:
        # Phone:(123）456-7890
        # --------------------------------------------------

        if normalized.startswith(
            "phone:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            # Normalize OCR full-width parenthesis
            value = (
                value
                .replace("）", ")")
                .replace("（", "(")
            )

            if value:

                result[
                    "hospital_phone"
                ] = value

            continue


        # --------------------------------------------------
        # Date of Birth
        #
        # OCR:
        # DateofBirth:01/01/1980
        # --------------------------------------------------

        if normalized.startswith(
            "dateofbirth:"
        ):

            match = re.search(
                r"\d{1,2}/\d{1,2}/\d{4}",
                text
            )

            if match:

                result[
                    "date_of_birth"
                ] = match.group()

            continue


        # --------------------------------------------------
        # Patient Address
        #
        # Important:
        # Only plain Address:, NOT HospitalAddress:
        # --------------------------------------------------

        if normalized.startswith(
            "address:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            if value:

                result[
                    "patient_address"
                ] = clean_collapsed_text(
                    value
                )

            continue


        # --------------------------------------------------
        # Main Receipt Date
        #
        # OCR:
        # Date:May16,2024
        #
        # Do not confuse with DateofBirth.
        # --------------------------------------------------

        if normalized.startswith(
            "date:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            if value:

                result[
                    "document_date"
                ] = value

            continue


        # --------------------------------------------------
        # Total Charges
        #
        # OCR:
        # TotalCharges:$2,500.00
        # --------------------------------------------------

        if normalized.startswith(
            "totalcharges:"
        ):

            match = re.search(
                r"[\d,]+(?:\.\d{2})?",
                text.split(
                    ":",
                    1
                )[1]
            )

            if match:

                result[
                    "total_amount"
                ] = (
                    match.group()
                    .replace(",", "")
                )

            continue


        # --------------------------------------------------
        # Amount Paid
        #
        # OCR:
        # Amount Paid: $2,500.00
        # --------------------------------------------------

        if normalized.startswith(
            "amountpaid:"
        ):

            match = re.search(
                r"[\d,]+(?:\.\d{2})?",
                text.split(
                    ":",
                    1
                )[1]
            )

            if match:

                result[
                    "amount_paid"
                ] = (
                    match.group()
                    .replace(",", "")
                )

            continue


        # --------------------------------------------------
        # Payment Method
        #
        # OCR:
        # PaymentMethod:CreditCard
        # --------------------------------------------------

        if normalized.startswith(
            "paymentmethod:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            if value:

                # Explicit trusted OCR cleanup
                known_payment_methods = {
                    "creditcard": "Credit Card",
                    "debitcard": "Debit Card",
                    "cash": "Cash",
                    "upi": "UPI",
                    "netbanking": "Net Banking",
                }

                key = (
                    value
                    .replace(" ", "")
                    .lower()
                )

                result[
                    "payment_method"
                ] = (
                    known_payment_methods
                    .get(
                        key,
                        value
                    )
                )

            continue


        # --------------------------------------------------
        # Transaction ID
        #
        # OCR:
        # TransactionID:123456789ABC
        # --------------------------------------------------

        if normalized.startswith(
            "transactionid:"
        ):

            value = text.split(
                ":",
                1
            )[1].strip()

            if value:

                result[
                    "transaction_id"
                ] = value

            continue


    # ==================================================
    # BLOCK-TEXT FALLBACKS
    # ==================================================
    #
    # Only used if rec_texts did not recover something.
    # ==================================================


    if not result["total_amount"]:

        match = re.search(
            r"Total\s*Charges\s*:\s*"
            r"[$₹₱]?\s*"
            r"([\d,]+(?:\.\d{2})?)",
            block_text,
            re.IGNORECASE
        )

        if match:

            result["total_amount"] = (
                match.group(1)
                .replace(",", "")
            )


    if not result["amount_paid"]:

        match = re.search(
            r"Amount\s*Paid\s*:\s*"
            r"[$₹₱]?\s*"
            r"([\d,]+(?:\.\d{2})?)",
            block_text,
            re.IGNORECASE
        )

        if match:

            result["amount_paid"] = (
                match.group(1)
                .replace(",", "")
            )


    # ==================================================
    # PAYMENT DATE
    # ==================================================
    #
    # Receipt has no separately labelled Payment Date.
    # Main receipt Date is the best available value.
    # ==================================================

    result["payment_date"] = (
        result["document_date"]
    )


        # ==================================================
    # RECEIPT 2 / TABLE-STYLE RECEIPT FALLBACKS
    # ==================================================

    # --------------------------------------------------
    # Payment Date
    # Example:
    # Payment Date | Nov 14, 2025
    # --------------------------------------------------

    if not result["payment_date"]:

        for i, text in enumerate(texts):

            normalized = re.sub(
                r"\s+",
                " ",
                str(text)
            ).strip()

            if normalized.lower() != "payment date":
                continue

            if i + 1 < len(texts):

                candidate = str(
                    texts[i + 1]
                ).strip()

                if candidate:
                    result["payment_date"] = candidate

            break


    # --------------------------------------------------
    # Payment Method
    # Example:
    # Payment Method | Cash
    # --------------------------------------------------

    if not result["payment_method"]:

        for i, text in enumerate(texts):

            normalized = re.sub(
                r"\s+",
                " ",
                str(text)
            ).strip()

            if normalized.lower() not in {
                "payment method",
                "payment mode",
            }:
                continue

            if i + 1 < len(texts):

                candidate = str(
                    texts[i + 1]
                ).strip()

                if candidate:

                    known_methods = {
                        "cash": "Cash",
                        "credit card": "Credit Card",
                        "creditcard": "Credit Card",
                        "debit card": "Debit Card",
                        "debitcard": "Debit Card",
                        "upi": "UPI",
                    }

                    key = candidate.lower()

                    result["payment_method"] = (
                        known_methods.get(
                            key,
                            candidate
                        )
                    )

            break


    # --------------------------------------------------
    # Tax Amount
    # --------------------------------------------------

    result["tax_amount"] = None

    for i, text in enumerate(texts):

        normalized = (
            str(text)
            .strip()
            .lower()
        )

        if normalized != "tax amount":
            continue

        for candidate in texts[
            i + 1:i + 4
        ]:

            match = re.search(
                r"[\d,]+(?:\.\d{2})?",
                str(candidate)
            )

            if match:

                result["tax_amount"] = (
                    match.group()
                    .replace(",", "")
                )

                break

        if result["tax_amount"]:
            break

    # ==================================================
    # BILL TO / PATIENT CONTACT DETAILS
    # ==================================================

    bill_to_index = None

    for i, text in enumerate(texts):

        if (
            str(text)
            .strip()
            .lower()
            == "bill to"
        ):
            bill_to_index = i
            break


    if bill_to_index is not None:

        # Only inspect a small region after Bill To.
        candidates = texts[
            bill_to_index + 1:
            bill_to_index + 8
        ]

        for candidate in candidates:

            value = str(
                candidate
            ).strip()

            if not value:
                continue


            # ------------------------------------------
            # Patient email
            # ------------------------------------------

            if not result["patient_email"]:

                match = re.search(
                    r"[A-Za-z0-9._%+\-]+"
                    r"@[A-Za-z0-9.\-]+"
                    r"\.[A-Za-z]{2,}",
                    value
                )

                if match:

                    result["patient_email"] = (
                        match.group()
                    )

                    continue


            # ------------------------------------------
            # Patient phone
            # ------------------------------------------

            if not result["patient_phone"]:

                match = re.search(
                    r"\(\d{3}\)\s*\d{3}-\d{4}",
                    value
                )

                if match:

                    result["patient_phone"] = (
                        match.group()
                    )

                    continue


            # ------------------------------------------
            # Patient address
            # ------------------------------------------

            if (
                not result["patient_address"]
                and re.search(
                    r"\d+\s+.+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Lane|Ln\.?)",
                    value,
                    re.IGNORECASE
                )
            ):

                result["patient_address"] = value

        # ==================================================
    # PROVIDER CONTACT FALLBACK
    # ==================================================

    hospital_index = None

    for i, text in enumerate(texts):

        lower = (
            str(text)
            .strip()
            .lower()
        )

        if (
            "hospital" in lower
            and "receipt" not in lower
        ):

            hospital_index = i
            break


    if hospital_index is not None:

        candidates = texts[
            hospital_index + 1:
            hospital_index + 7
        ]

        for candidate in candidates:

            value = str(
                candidate
            ).strip()

            if not value:
                continue


            # Provider phone
            if not result["hospital_phone"]:

                match = re.search(
                    r"\(\d{3}\)\s*\d{3}-\d{4}",
                    value
                )

                if match:

                    result["hospital_phone"] = (
                        match.group()
                    )

                    continue


            # Provider address
            if (
                not result["hospital_address"]
                and re.search(
                    r"\d+\s+.+(?:Ave|Avenue|Street|St\.?|Road|Rd\.?)",
                    value,
                    re.IGNORECASE
                )
            ):

                result["hospital_address"] = value

    # ==================================================
    # RECEIPT 2 - BILL TO / PAYMENT OCR FALLBACK
    # ==================================================

    # --------------------------------------------------
    # Find Jane-style Bill To section
    # --------------------------------------------------

    bill_to_index = None

    for i, text in enumerate(texts):

        normalized = (
            str(text)
            .strip()
            .lower()
        )

        if normalized == "bill to":
            bill_to_index = i
            break


    if bill_to_index is not None:

        # Receipt OCR may interleave Receipt No.,
        # patient information and payment information.
        nearby = texts[
            bill_to_index + 1:
            bill_to_index + 15
        ]

        # --------------------------------------------------
        # Patient Email
        # --------------------------------------------------

        if not result["patient_email"]:

            for candidate in nearby:

                candidate = str(
                    candidate
                ).strip()

                match = re.fullmatch(
                    r"[A-Za-z0-9._%+\-]+"
                    r"@[A-Za-z0-9.\-]+"
                    r"\.[A-Za-z]{2,}",
                    candidate
                )

                if match:

                    # Do not accidentally use provider email
                    if (
                        "citycarehospital"
                        not in candidate.lower()
                    ):

                        result["patient_email"] = (
                            candidate
                        )

                        break


        # --------------------------------------------------
        # Patient Phone
        # --------------------------------------------------

        if not result["patient_phone"]:

            for candidate in nearby:

                candidate = str(
                    candidate
                ).strip()

                match = re.fullmatch(
                    r"\(\d{3}\)\s*\d{3}-\d{4}",
                    candidate
                )

                if match:

                    result["patient_phone"] = (
                        candidate
                    )

                    break


        # --------------------------------------------------
        # Patient Address + split ZIP
        #
        # OCR:
        # 456 Elm Street, Apt 12, Wellness City, State
        # ...
        # 45678
        # --------------------------------------------------

        address_index = None

        for local_index, candidate in enumerate(
            nearby
        ):

            candidate = str(
                candidate
            ).strip()

            if re.search(
                r"\d+\s+.+"
                r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?)",
                candidate,
                re.IGNORECASE
            ):

                result["patient_address"] = (
                    candidate
                )

                address_index = (
                    local_index
                )

                break


        # Search a few following OCR items for ZIP.
        if (
            result["patient_address"]
            and address_index is not None
        ):

            zip_candidates = nearby[
                address_index + 1:
                address_index + 5
            ]

            for candidate in zip_candidates:

                candidate = str(
                    candidate
                ).strip()

                if re.fullmatch(
                    r"\d{5,6}",
                    candidate
                ):

                    # Only append if ZIP isn't already there.
                    if not re.search(
                        r"\b\d{5,6}\b$",
                        result["patient_address"]
                    ):

                        result["patient_address"] = (
                            result["patient_address"]
                            + " "
                            + candidate
                        )

                    break


        # ==================================================
    # PAYMENT METHOD
    # ==================================================

    if not result["payment_method"]:

        known_methods = {
            "cash": "Cash",
            "credit card": "Credit Card",
            "creditcard": "Credit Card",
            "debit card": "Debit Card",
            "debitcard": "Debit Card",
            "upi": "UPI",
            "net banking": "Net Banking",
            "netbanking": "Net Banking",
        }

        for i, text in enumerate(texts):

            normalized_label = re.sub(
                r"[^a-z]",
                "",
                str(text).lower()
            )

            # Handles:
            # PaymentMethod
            # ymentMethod
            if (
                "paymentmethod" not in normalized_label
                and "ymentmethod" not in normalized_label
            ):
                continue

            # OCR can place the payment value
            # several positions before/after the label.
            start = max(
                0,
                i - 5
            )

            end = min(
                len(texts),
                i + 6
            )

            nearby = texts[
                start:end
            ]

            for candidate in nearby:

                candidate = str(
                    candidate
                ).strip()

                key = re.sub(
                    r"[^a-z]",
                    "",
                    candidate.lower()
                )

                if key in known_methods:
                    result["payment_method"] = (
                        known_methods[key]
                    )
                    break

            if result["payment_method"]:
                break
    return result

def extract_claim_fields_v3(structured_results):

    rich = extract_rich_invoice_details_v3(
        structured_results
    )

    receipt = extract_rich_receipt_details_v3(
        structured_results
    )
    
    return {
        "hospital_name": (
            extract_rich_hospital_name_v3(structured_results)
            or extract_hospital_name_v3(structured_results)
        ),

        "patient_name": (
            rich["patient_name"]
            or extract_patient_name_v3(
              structured_results
        )
    ),

        "patient_id": (
           rich["patient_id"]
           or extract_patient_id_v3(
              structured_results
        )
    ),
        "date_of_birth":
           receipt["date_of_birth"],

"patient_phone": receipt["patient_phone"],
"patient_email": receipt["patient_email"],
        
        "patient_address":
           receipt["patient_address"],

        "age":
            rich["age"],

        "gender":
            rich["gender"],

        "member_id":
            rich["member_id"],

        "policy_number":
            rich["policy_number"],

        "policyholder_name":
            rich["policyholder_name"],

        "relationship":
            rich["relationship"],

        "insurer_name":
            rich["insurer_name"],

        "tpa_name":
            rich["tpa_name"],

        "hospital_address": (
           receipt["hospital_address"]
           or rich["hospital_address"]
        ),

        "hospital_phone": (
    receipt["hospital_phone"]
    or rich["hospital_phone"]
),
"hospital_email": rich["hospital_email"],
"hospital_gstin": rich["hospital_gstin"],

"admission_number": rich["admission_number"],
"admission_time": rich["admission_time"],
"discharge_time": rich["discharge_time"],
"room_category": rich["room_category"],

"doctor_name": rich["doctor_name"],
"specialization": rich["specialization"],
"diagnosis": rich["diagnosis"],
"procedure": rich["procedure"],
"subtotal": rich["subtotal"],
"discount": rich["discount"],
"tax_amount": (
    receipt["tax_amount"]
    or rich["tax_amount"]
),

"amount_approved": rich["amount_approved"],
"copay_amount": rich["copay_amount"],
"amount_paid": rich["amount_paid"],

"payment_method": (
    receipt["payment_method"]
    or rich["payment_method"]
),
"transaction_id": rich["transaction_id"],
"payment_date": rich["payment_date"],

        "document_number":
            extract_document_number_v3(
                structured_results
            ),

        "document_date": (
    receipt["document_date"]
    or extract_service_date_v3(
        structured_results
    )
),
        "service_date":
            extract_service_date_v3(
                structured_results
            ),

        "admission_date": (
            rich.get("admission_date")
            or extract_admission_date_v3(structured_results)
        ),

        "discharge_date": (
            rich.get("discharge_date")
            or extract_discharge_date_v3(structured_results)
        ),

        "total_amount": (
    receipt["total_amount"]
    or extract_rich_total_amount_v3(
        structured_results
    )
    or extract_total_amount_v3(
        structured_results
    )
),

        "amount_paid": (
    receipt["amount_paid"]
    or rich["amount_paid"]
),

"payment_method": (
    receipt["payment_method"]
    or rich["payment_method"]
),

"transaction_id": (
    receipt["transaction_id"]
    or rich["transaction_id"]
),

"payment_date": (
    receipt["payment_date"]
    or rich["payment_date"]
),

        "currency":
            extract_currency_v3(
                structured_results
            ),

        "line_items":
            extract_claim_lines_v3(
                structured_results
            ),
    }

def extract_hospital_name_v3(structured_results):

    texts = get_all_text(structured_results)

    # Case 1:
    # HospitalName:CityHealthHospital
    # Hospital Name: City Health Hospital
    for text in texts:

        match = re.search(
            r"hospital\s*name\s*:\s*(.+)",
            text,
            re.IGNORECASE
        )

        if match:
            value = match.group(1).strip()

            if value:
                return value

    # Case 2:
    # Hospital Name
    # City Care Hospital
    for i, text in enumerate(texts):

        lower = text.lower().strip()

        if lower in (
            "hospital name",
            "hospital name:",
        ):

            if i + 1 < len(texts):
                value = texts[i + 1].strip()

                if value:
                    return value

    # Case 3:
    # Existing invoice headings
    for text in texts[:20]:

        lower = text.lower()

        if "hospital" in lower or "hospitals" in lower:

            # Don't accept generic receipt title
            if lower.strip() in (
                "hospital",
                "hospital bill",
                "hospital bill payment receipt",
            ):
                continue

            return text.strip()

    return None

def extract_rich_hospital_name_v3(structured_results):
    block_text = get_block_text(structured_results)
    if not block_text:
        return None

    lines = [re.sub(r"\s+", " ", line).strip() for line in block_text.splitlines() if line.strip()]

    # Prefer a legal provider name ending in Private Limited / Pvt. Ltd.
    for line in lines:
        match = re.search(
            r"(?:For\s+)?([A-Za-z][A-Za-z&.'\-]*(?:\s+[A-Za-z][A-Za-z&.'\-]*)*\s+Hospitals\s+(?:Private\s+Limited|Pvt\.?\s+Ltd\.?))",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    # Then prefer Multispeciality Hospitals (Invoice 1).
    for line in lines:
        match = re.search(
            r"(?:For\s+)?([A-Za-z][A-Za-z&.'\-]*(?:\s+[A-Za-z][A-Za-z&.'\-]*)*\s+Multispeciality\s+Hospitals)",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    return None

def extract_patient_id_v3(structured_results):

    texts = get_all_text(structured_results)

    # PatientID:001234567
    # Patient ID: 001234567
    for text in texts:

        match = re.search(
            r"patient\s*id\s*:\s*([A-Za-z0-9\-]+)",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

    labels = [
        "patient id",
        "patient code",
        "uhid",
        "mrn",
    ]

    for i, text in enumerate(texts):

        lower = text.lower()

        if any(label in lower for label in labels):

            parts = re.split(
                r":",
                text,
                maxsplit=1
            )

            if (
                len(parts) > 1
                and parts[1].strip()
            ):
                return parts[1].strip()

            if i + 1 < len(texts):
                return texts[i + 1].strip()

    return None

def extract_date_from_label(
    structured_results,
    labels
):

    texts = get_all_text(structured_results)

    date_pattern = (
        r"\d{1,2}\s*[-/]\s*"
        r"[A-Za-z]{3,9}\s*[-/]\s*"
        r"\d{2,4}"
        r"|"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{1,2}\s*[-/]\s*"
        r"\d{2,4}"
        r"|"
        r"[A-Za-z]{3,9}\s*"
        r"\d{1,2},?\s*\d{4}"
    )

    for i, text in enumerate(texts):

        lower = text.lower().strip()

        if any(
            label in lower
            for label in labels
        ):

            match = re.search(
                date_pattern,
                text,
                re.IGNORECASE
            )

            if match:
                return match.group().strip()

            if i + 1 < len(texts):

                match = re.search(
                    date_pattern,
                    texts[i + 1],
                    re.IGNORECASE
                )

                if match:
                    return match.group().strip()

    return None

def extract_service_date_v3(structured_results):

    return extract_date_from_label(
        structured_results,
        [
            "service date",
            "invoice date",
            "bill date",
            "bill dt",
            "billdt",
            "bill issue date",
            "billissue date",       # OCR/layout variation
            "payment date",
        ]
    )

def extract_admission_date_v3(structured_results):
    block_text = get_block_text(structured_results)
    texts = get_all_text(structured_results)
    date_pattern = r"\d{1,2}\s*[-/]\s*[A-Za-z]{3,9}\s*[-/]\s*\d{4}|\d{1,2}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{4}"

    match = re.search(rf"Admission\s+Date(?:\s*&\s*Time)?\s*:?\s*({date_pattern})", block_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    for text in texts:
        lower = text.lower().replace(" ", "")
        if "admission" in lower or "admssion" in lower or "admbsion" in lower:
            match = re.search(date_pattern, text, re.IGNORECASE)
            if match:
                return match.group().strip()
    return None

def extract_discharge_date_v3(structured_results):
    block_text = get_block_text(structured_results)
    texts = get_all_text(structured_results)
    date_pattern = r"\d{1,2}\s*[-/]\s*[A-Za-z]{3,9}\s*[-/]\s*\d{4}|\d{1,2}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{4}"

    match = re.search(rf"Discharge\s+Date(?:\s*&\s*Time)?\s*:?\s*({date_pattern})", block_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    for text in texts:
        lower = text.lower().replace(" ", "")
        if any(x in lower for x in ("discharge", "discahrge", "dicahrge", "dischage", "dischrge")):
            match = re.search(date_pattern, text, re.IGNORECASE)
            if match:
                return match.group().strip()
    return None

def extract_total_amount_v3(structured_results):

    texts = get_all_text(
        structured_results
    )

    # ==================================================
    # BILL AMOUNT
    # Highest priority for traditional inpatient bills
    # ==================================================

    for i, text in enumerate(texts):

        normalized = re.sub(
            r"\s+",
            " ",
            str(text)
        ).strip()

        if not re.search(
            r"\bbill\s*amount\b",
            normalized,
            re.IGNORECASE
        ):
            continue

        # ----------------------------------------------
        # Amount may be in same OCR item
        # ----------------------------------------------

        match = re.search(
            r"[\d,]+\.\d{2}",
            normalized
        )

        if match:

            return (
                match.group()
                .replace(",", "")
            )

        # ----------------------------------------------
        # Or immediately after the label
        # ----------------------------------------------

        for candidate in texts[
            i + 1:i + 5
        ]:

            candidate = str(
                candidate
            ).strip()

            match = re.search(
                r"[\d,]+\.\d{2}",
                candidate
            )

            if match:

                return (
                    match.group()
                    .replace(",", "")
                )

    # ==================================================
    # KEEP ALL YOUR EXISTING TOTAL LOGIC BELOW THIS
    # ==================================================
    # Rich invoice: NET PAYABLE

    for i, text in enumerate(texts):

      normalized_label = re.sub(
        r"[^a-z]",
        "",
        text.lower()
    )

      if "netpayable" not in normalized_label:
        continue

    # Amount may be in same OCR item
    match = re.search(
        r"[\d,]+\.\d{2}",
        text
    )

    if match:
        return (
            match.group()
            .replace(",", "")
        )

    # Or in one of the next few OCR items
    for candidate in texts[i + 1:i + 4]:

        match = re.search(
            r"[\d,]+\.\d{2}",
            candidate
        )

        if match:
            return (
                match.group()
                .replace(",", "")
            )

    # -----------------------------------------
    # Receipt style:
    # TotalCharges:$2,500.00
    # -----------------------------------------

    for text in texts:

        match = re.search(
            r"total\s*charges\s*:\s*"
            r"[$₹₱]?\s*"
            r"([\d,]+(?:\.\d{2})?)",
            text,
            re.IGNORECASE
        )

        if match:
            return (
                match.group(1)
                .replace(",", "")
            )

    # -----------------------------------------
    # Existing invoice styles
    # -----------------------------------------

    labels = [
        "bill amount",
        "total amount",
        "total amount due",
        "grand total",
        "net amount",
        "amount payable",
        "total charges",
    ]

    amount_pattern = (
        r"(?:[$₹₱]\s*)?"
        r"[\d,]+\.\d{2}"
    )

    for i, text in enumerate(texts):

        lower = text.lower()

        if any(
            label in lower
            for label in labels
        ):

            match = re.search(
                amount_pattern,
                text
            )

            if match:

                return (
                    match.group()
                    .replace("$", "")
                    .replace("₹", "")
                    .replace("₱", "")
                    .replace(",", "")
                    .strip()
                )

            if i + 1 < len(texts):

                match = re.search(
                    amount_pattern,
                    texts[i + 1]
                )

                if match:

                    return (
                        match.group()
                        .replace("$", "")
                        .replace("₹", "")
                        .replace("₱", "")
                        .replace(",", "")
                        .strip()
                    )

    return None

def extract_currency_v3(structured_results):

    texts = get_all_text(structured_results)

    full_text = " ".join(texts).lower()

    if "$" in full_text or "usd" in full_text:
        return "USD"

    if "₱" in full_text or "php" in full_text:
        return "PHP"

    if "₹" in full_text or "inr" in full_text or "amount(rs" in full_text:
        return "INR"

    # Your chosen fallback
    return "INR"

def extract_rich_total_amount_v3(structured_results):
    block_text = get_block_text(structured_results)
    if not block_text:
        return None

    # Explicit total labels first.
    total_patterns = [
        r"NET\s*PAYABLE",
        r"Gross\s+Bill\s+Amount",
        r"Grand\s+Total",
        r"Total\s+Amount\s+Due",
        r"Amount\s+Payable",
    ]
    for label in total_patterns:
        match = re.search(rf"{label}.{0,120}?([\d,]+\.\d{{2}})", block_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).replace(",", "")

    # Cashless invoice fallback: insurer-approved + patient payable/co-pay.
    approved = re.search(r"Amount\s+Approved\s+by\s+Insurer.{0,120}?([\d,]+\.\d{2})", block_text, re.IGNORECASE | re.DOTALL)
    copay = re.search(r"Patient\s+Payable\s*/\s*Co-pay(?:\s*/\s*Non\s+Payable)?.{0,120}?([\d,]+\.\d{2})", block_text, re.IGNORECASE | re.DOTALL)
    if approved and copay:
        try:
            return str(float(approved.group(1).replace(",", "")) + float(copay.group(1).replace(",", "")))
        except ValueError:
            pass

    return None

def extract_claim_lines_v3(structured_results):

    texts = get_all_text(structured_results)

    # ==================================================
    # METHOD 0
    # Receipt-style service list
    # ==================================================

    for i, text in enumerate(texts):

        lower = text.lower().strip()

        if (
            "services provided" in lower
            or "service provided" in lower
        ):

            line_items = []

            for candidate in texts[i + 1:i + 15]:

                match = re.match(
                    r"(.+?)\s*:\s*"
                    r"[$₹₱]?\s*"
                    r"([\d,]+(?:\.\d{2})?)$",
                    candidate.strip(),
                    re.IGNORECASE
                )

                if not match:
                    continue

                description = (
                    match.group(1)
                    .strip()
                )

                amount = float(
                    match.group(2)
                    .replace(",", "")
                )

                line_items.append({
                    "lineNumber":
                        len(line_items) + 1,

                    "description":
                        description,

                    "hsnCode":
                        None,

                    "quantity":
                        None,

                    "unitRate":
                        None,

                    "amount":
                        amount,
                })

            if line_items:
                return line_items


    # ==================================================
    # HTML TABLE SUPPORT
    # ==================================================

    from html.parser import HTMLParser


    # --------------------------------------------------
    # Find all PPStructure table results
    # --------------------------------------------------

    def find_tables(obj):

        tables = []

        if isinstance(obj, dict):

            for key, value in obj.items():

                if (
                    key == "table_res_list"
                    and isinstance(value, list)
                ):

                    tables.extend(value)

                else:

                    tables.extend(
                        find_tables(value)
                    )

        elif isinstance(obj, list):

            for item in obj:

                tables.extend(
                    find_tables(item)
                )

        return tables


    # --------------------------------------------------
    # HTML table parser
    # --------------------------------------------------

    class TableParser(HTMLParser):

        def __init__(self):

            super().__init__()

            self.rows = []
            self.current_row = []
            self.current_cell = ""
            self.in_cell = False


        def handle_starttag(
            self,
            tag,
            attrs
        ):

            if tag in (
                "td",
                "th"
            ):

                self.in_cell = True
                self.current_cell = ""


        def handle_data(
            self,
            data
        ):

            if self.in_cell:

                self.current_cell += data


        def handle_endtag(
            self,
            tag
        ):

            if tag in (
                "td",
                "th"
            ):

                self.current_row.append(
                    self.current_cell.strip()
                )

                self.current_cell = ""
                self.in_cell = False

            elif tag == "tr":

                if self.current_row:

                    self.rows.append(
                        self.current_row
                    )

                self.current_row = []


    # --------------------------------------------------
    # Amount cleaner
    # --------------------------------------------------

    def clean_amount(value):

        if value is None:
            return None

        cleaned = str(value)

        cleaned = (
            cleaned
            .replace("$", "")
            .replace("₹", "")
            .replace("₱", "")
            .replace(",", "")
            .strip()
        )

        # Remove OCR currency noise while preserving
        # numeric characters, decimal point and minus.
        cleaned = re.sub(
            r"[^0-9.\-]",
            "",
            cleaned
        )

        if not cleaned:
            return None

        try:

            return float(cleaned)

        except ValueError:

            return None


    tables = find_tables(
        structured_results
    )

    best_claim_lines = []


    # ==================================================
    # METHOD 1
    # Reconstructed HTML tables
    # ==================================================

    for table in tables:

        html = table.get(
            "pred_html"
        )

        if not html:
            continue

        parser = TableParser()

        try:

            parser.feed(html)

        except Exception:

            continue

        rows = parser.rows

        if not rows:
            continue


        # ----------------------------------------------
        # Find service-table header
        # ----------------------------------------------

        header_index = None

        for row_index, row in enumerate(rows):

            normalized = [
                cell.lower().strip()
                for cell in row
            ]

            combined_header = " ".join(
                normalized
            )

            has_description = any(
                header in normalized
                for header in (
                    "description",
                    "description of service",
                    "service name",
                    "service",
                    "item",
                    "particulars",
                )
            )

            has_amount = (
                "amount" in combined_header
            )

            if (
                has_description
                and has_amount
            ):

                header_index = row_index
                break


        if header_index is None:
            continue


        headers = [
            cell.lower().strip()
            for cell in rows[
                header_index
            ]
        ]


        # ----------------------------------------------
        # Identify columns
        # ----------------------------------------------

        description_index = None
        hsn_index = None
        quantity_index = None
        unit_rate_index = None
        amount_index = None


        for column_index, header in enumerate(
            headers
        ):

            header_clean = (
                header
                .lower()
                .strip()
            )

            # Description
            if header_clean in (
                "description",
                "description of service",
                "service name",
                "service",
                "item",
                "particulars",
            ):

                description_index = (
                    column_index
                )


            # HSN / SAC
            elif (
                "hsn" in header_clean
                or "sac" in header_clean
            ):

                hsn_index = (
                    column_index
                )


            # Quantity / Days
            elif (
                "quantity" in header_clean
                or "qty" in header_clean
            ):

                quantity_index = (
                    column_index
                )


            # Unit rate
            elif (
               "unit rate" in header_clean
               or "unit price" in header_clean
               or "unit cost" in header_clean
               or header_clean == "rate"
            ):
               unit_rate_index = column_index


            # Final amount
            elif "amount" in header_clean:

                amount_index = (
                    column_index
                )


        # Description and final amount are mandatory.
        if (
            description_index is None
            or amount_index is None
        ):

            continue


        # ----------------------------------------------
        # Extract service rows
        # ----------------------------------------------

        claim_lines = []


        skip_descriptions = {
            "subtotal",
            "sub total",
            "tax",
            "tax amount",
            "taxable amount",
            "discount",
            "cgst",
            "sgst",
            "round off",
            "grand total",
            "net payable",
            "total",
            "total amount",
            "total amount due",
            "bill amount",
            "gross bill amount",
        }


        for row in rows[
            header_index + 1:
        ]:

            required_max_index = max(
                description_index,
                amount_index
            )

            if len(row) <= required_max_index:
                continue


            # ------------------------------------------
            # Description
            # ------------------------------------------

            description = (
                row[
                    description_index
                ]
                .strip()
            )

            if not description:
                continue


            description_normalized = (
                description
                .lower()
                .strip()
            )

            if (
                description_normalized
                in skip_descriptions
            ):

                continue


            # Also skip summary-like descriptions
            if any(
                description_normalized.startswith(
                    prefix
                )
                for prefix in (
                    "subtotal",
                    "sub total",
                    "discount",
                    "taxable amount",
                    "cgst",
                    "sgst",
                    "round off",
                    "net payable",
                    "grand total",
                )
            ):

                continue


            # ------------------------------------------
            # Amount
            # ------------------------------------------

            amount = clean_amount(
                row[
                    amount_index
                ]
            )

            if amount is None:
                continue


            # ------------------------------------------
            # HSN Code
            # ------------------------------------------

            hsn_code = None

            if (
                hsn_index is not None
                and hsn_index < len(row)
            ):

                hsn_text = (
                    row[
                        hsn_index
                    ]
                    .strip()
                )

                if hsn_text:

                    hsn_code = (
                        hsn_text
                    )


            # ------------------------------------------
            # Quantity / Days
            # ------------------------------------------

            quantity = None

            if (
                quantity_index is not None
                and quantity_index < len(row)
            ):

                quantity_text = (
                    row[
                        quantity_index
                    ]
                    .strip()
                )

                if quantity_text:

                    quantity = (
                        quantity_text
                    )


            # ------------------------------------------
            # Unit Rate
            # ------------------------------------------

            unit_rate = None

            if (
                unit_rate_index is not None
                and unit_rate_index < len(row)
            ):

                unit_rate = clean_amount(
                    row[
                        unit_rate_index
                    ]
                )


            # ------------------------------------------
            # Add line
            # ------------------------------------------

            claim_lines.append({

                "lineNumber":
                    len(claim_lines) + 1,

                "description":
                    description,

                "hsnCode":
                    hsn_code,

                "quantity":
                    quantity,

                "unitRate":
                    unit_rate,

                "amount":
                    amount,
            })


        # Keep the best table.
        if (
            len(claim_lines)
            > len(best_claim_lines)
        ):

            best_claim_lines = (
                claim_lines
            )


    # ==================================================
    # METHOD 2
    # Coordinate fallback
    #
    # Primarily preserves support for older documents
    # whose HTML reconstruction is weaker.
    # ==================================================

    for table in tables:

        table_ocr = table.get(
            "table_ocr_pred",
            {}
        )

        texts = table_ocr.get(
            "rec_texts",
            []
        )

        boxes = table_ocr.get(
            "rec_boxes",
            []
        )

        if not texts or not boxes:
            continue


        combined = (
            " ".join(
                str(text)
                for text in texts
            )
            .lower()
        )


        # This fallback currently targets the older
        # Service Name / Amount layout.
        if (
            "service name" not in combined
        ):

            continue


        descriptions = []
        amounts = []


        for text, box in zip(
            texts,
            boxes
        ):

            text = str(
                text
            ).strip()

            if not text:
                continue


            if text.lower() in {
                "details",
                "service name",
                "amount(rs.)",
                "amount",
                "subtotal",
                "sub total",
                "tax",
                "tax amount",
                "grand total",
                "total",
                "total amount",
                "total amount due",
                "bill amount",
            }:

                continue


                        # Do not treat payment/deposit/footer text
            # as medical service lines.
            text_lower = text.lower()

            if any(
                phrase in text_lower
                for phrase in (
                    "refundable deposit",
                    "deposit as on",
                    "amount in words",
                    "in words",
                    "payment",
                    "transaction",
                    "reference no",
                )
            ):
                continue

            amount = clean_amount(
                text
            )


            if amount is not None:

                amounts.append({

                    "amount":
                        amount,

                    "y":
                        box[1],
                })

            else:

                descriptions.append({

                    "description":
                        text,

                    "y":
                        box[1],
                })


        claim_lines = []

        used_amounts = set()


        for description in descriptions:

            candidates = []


            for amount_index_candidate, amount_data in enumerate(
                amounts
            ):

                if (
                    amount_index_candidate
                    in used_amounts
                ):

                    continue


                distance = abs(
                    description["y"]
                    - amount_data["y"]
                )


                candidates.append(
                    (
                        distance,
                        amount_index_candidate,
                        amount_data,
                    )
                )


            if not candidates:
                continue


            (
                distance,
                selected_index,
                selected_amount
            ) = min(
                candidates,
                key=lambda candidate:
                    candidate[0]
            )


            if distance > 50:
                continue


            used_amounts.add(
                selected_index
            )

            description_text = (
                description["description"]
                .strip()
            )

            description_lower = (
                description_text.lower()
            )

            if any(
                phrase in description_lower
                for phrase in (
                    "refundable deposit",
                    "deposit as on",
                    "amount in words",
                    "in words",
                )
            ):
                continue

            claim_lines.append({

                "lineNumber":
                    len(claim_lines) + 1,

                "description":
                    description[
                        "description"
                    ],

                "hsnCode":
                    None,

                "quantity":
                    None,

                "unitRate":
                    None,

                "amount":
                    selected_amount[
                        "amount"
                    ],
            })


        if (
            len(claim_lines)
            > len(best_claim_lines)
        ):

            best_claim_lines = (
                claim_lines
            )

        # ==================================================
    # RECEIPT ITEMIZED TABLE FALLBACK
    # ==================================================
    #
    # Handles receipt tables such as:
    #
    # Qty | Description | Unit Price | Amount
    #
    # Used only when it finds MORE valid rows than
    # the existing extraction logic.
    # ==================================================

    receipt_lines = []

    for table in tables:

        html = table.get("pred_html")

        if not html:
            continue

        parser = TableParser()

        try:
            parser.feed(html)
        except Exception:
            continue

        rows = parser.rows

        if not rows:
            continue


        # ----------------------------------------------
        # Find receipt table header
        # ----------------------------------------------

        header_index = None

        for row_index, row in enumerate(rows):

            normalized = [
                re.sub(
                    r"\s+",
                    " ",
                    str(cell).lower().strip()
                )
                for cell in row
            ]

            combined = " ".join(normalized)

            has_description = (
                "description" in combined
            )

            has_quantity = (
                "qty" in combined
                or "quantity" in combined
            )

            has_amount = (
                "amount" in combined
            )

            if (
                has_description
                and has_quantity
                and has_amount
            ):
                header_index = row_index
                break


        if header_index is None:
            continue


        headers = [
            re.sub(
                r"\s+",
                " ",
                str(cell).lower().strip()
            )
            for cell in rows[header_index]
        ]


        description_index = None
        quantity_index = None
        unit_rate_index = None
        amount_index = None


        for index, header in enumerate(headers):

            if "description" in header:
                description_index = index

            elif (
                header == "qty"
                or "quantity" in header
            ):
                quantity_index = index

            elif (
                "unit price" in header
                or "unit rate" in header
                or header == "rate"
            ):
                unit_rate_index = index

            elif "amount" in header:
                amount_index = index


        if (
            description_index is None
            or amount_index is None
        ):
            continue


        current_lines = []


        # ----------------------------------------------
        # Extract ALL service rows
        # ----------------------------------------------

        for row in rows[header_index + 1:]:

            max_required = max(
                description_index,
                amount_index
            )

            if len(row) <= max_required:
                continue


            description = str(
                row[description_index]
            ).strip()


            if not description:
                continue


            description_lower = (
                description.lower()
            )


            # Stop/skip financial summary rows
            if any(
                phrase in description_lower
                for phrase in (
                    "subtotal",
                    "tax amount",
                    "total amount",
                    "grand total",
                    "payment method",
                    "payment date",
                    "amount in words",
                )
            ):
                continue


            amount = clean_amount(
                row[amount_index]
            )


            if amount is None:
                continue


            quantity = None

            if (
                quantity_index is not None
                and quantity_index < len(row)
            ):
                value = str(
                    row[quantity_index]
                ).strip()

                if value:
                    quantity = value


            unit_rate = None

            if (
                unit_rate_index is not None
                and unit_rate_index < len(row)
            ):
                unit_rate = clean_amount(
                    row[unit_rate_index]
                )


            current_lines.append({
                "lineNumber":
                    len(current_lines) + 1,

                "description":
                    description,

                "hsnCode":
                    None,

                "quantity":
                    quantity,

                "unitRate":
                    unit_rate,

                "amount":
                    amount,
            })


        # Only replace existing extraction if
        # this method actually found more rows.
        if (
            len(current_lines)
            > len(receipt_lines)
        ):
            receipt_lines = current_lines


    if (
        len(receipt_lines)
        > len(best_claim_lines)
    ):
        best_claim_lines = receipt_lines

    # ==================================================
    # FINAL RESULT
    # ==================================================

    return best_claim_lines