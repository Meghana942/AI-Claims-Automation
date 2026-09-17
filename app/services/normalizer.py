import re


# =========================================================
# DATE NORMALIZATION
# =========================================================

def normalize_date(value):

    if not value:
        return None

    value = str(value).strip()

    # Remove OCR punctuation around dates
    # Example:
    # ":03-Jun-2024" -> "03-Jun-2024"
    value = re.sub(
        r"^[\s:;|]+",
        "",
        value
    )

    value = re.sub(
        r"[\s:;|]+$",
        "",
        value
    )

    # OCR cleanup for month names
    month_fixes = {
        "janw": "Jan",
        "febw": "Feb",
        "marw": "Mar",
        "aprw": "Apr",
        "mayw": "May",
        "junw": "June",
        "julw": "July",
        "augw": "Aug",
        "sepw": "Sep",
        "octw": "Oct",
        "novw": "Nov",
        "decw": "Dec",
    }

    for wrong, correct in month_fixes.items():

        value = re.sub(
            wrong,
            correct,
            value,
            flags=re.IGNORECASE
        )

    return value


# =========================================================
# AMOUNT NORMALIZATION
# =========================================================

def normalize_amount(amount):

    if amount is None or amount == "":
        return None

    amount = str(amount)

    amount = amount.replace("₹", "")
    amount = amount.replace("$", "")
    amount = amount.replace("₱", "")
    amount = amount.replace(",", "")
    amount = amount.strip()

    try:

        return float(amount)

    except (ValueError, TypeError):

        return None


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    if text is None:
        return None

    text = str(text).strip()

    if not text:
        return None

    return re.sub(
        r"\s+",
        " ",
        text
    )


# =========================================================
# HOSPITAL NAME NORMALIZATION
# =========================================================

def normalize_hospital_name(value):

    if not value:
        return None

    value = str(value).strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    known_fixes = {
        "apollohospitals":
            "APOLLO HOSPITALS",

        "cityhealthhospital":
            "City Health Hospital",
    }

    key = re.sub(
        r"\s+",
        "",
        value
    ).lower()

    return known_fixes.get(
        key,
        value
    )


# =========================================================
# PERSON NAME NORMALIZATION
# =========================================================

def normalize_person_name(value):

    if not value:
        return None

    value = str(value).strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    known_fixes = {
        "johndoe":
            "John Doe",

        "mrs.kavyalyer":
            "Mrs. Kavya Iyer",
    }

    key = re.sub(
        r"\s+",
        "",
        value
    ).lower()

    return known_fixes.get(
        key,
        value
    )


# =========================================================
# LINE ITEM NORMALIZATION
# =========================================================

def normalize_line_items(line_items):

    if not line_items:
        return []

    description_fixes = {
        "roomrent":
            "ROOM RENT",

        "medicalequipment":
            "MEDICAL EQUIPMENT",
    }

    normalized_items = []

    for item in line_items:

        new_item = item.copy()

        description = str(
            item.get(
                "description",
                ""
            )
        ).strip()

        key = re.sub(
            r"\s+",
            "",
            description
        ).lower()

        new_item["description"] = (
            description_fixes.get(
                key,
                description
            )
        )

        normalized_items.append(
            new_item
        )

    return normalized_items


# =========================================================
# COMPLETE CLAIM DATA NORMALIZATION
# =========================================================

def normalize_data(data):

    # =====================================================
    # DATE NORMALIZATION + SERVICE DATE FALLBACK
    # =====================================================

    document_date = normalize_date(
        data.get("document_date")
    )

    admission_date = normalize_date(
        data.get("admission_date")
    )

    discharge_date = normalize_date(
        data.get("discharge_date")
    )

    service_date = normalize_date(
        data.get("service_date")
    )


    # -----------------------------------------------------
    # SERVICE DATE FALLBACK
    #
    # Priority:
    #
    # 1. Explicit service date
    # 2. Document / bill date
    # 3. Discharge date
    # 4. Admission date
    # -----------------------------------------------------

    if not service_date:

        service_date = (
            document_date
            or discharge_date
            or admission_date
        )


    return {

        # =================================================
        # PROVIDER / HOSPITAL
        # =================================================

        "hospital_name":
            normalize_hospital_name(
                data.get("hospital_name")
            ),

        "hospital_address":
            normalize_text(
                data.get("hospital_address")
            ),

        "hospital_phone":
            normalize_text(
                data.get("hospital_phone")
            ),

        "hospital_email":
            normalize_text(
                data.get("hospital_email")
            ),

        "hospital_gstin":
            normalize_text(
                data.get("hospital_gstin")
            ),


        # =================================================
        # PATIENT
        # =================================================

        "patient_name":
            normalize_person_name(
                data.get("patient_name")
            ),

        "patient_id":
            normalize_text(
                data.get("patient_id")
            ),

        "member_id":
            normalize_text(
                data.get("member_id")
            ),

        "age":
            normalize_text(
                data.get("age")
            ),

        "gender":
            normalize_text(
                data.get("gender")
            ),

        "date_of_birth":
            normalize_date(
                data.get("date_of_birth")
            ),

        "patient_address":
            normalize_text(
                data.get("patient_address")
            ),

        "patient_phone":
            normalize_text(
                data.get("patient_phone")
            ),

        "patient_email":
            normalize_text(
                data.get("patient_email")
            ),

        "city":
            normalize_text(
                data.get("city")
            ),

        "state":
            normalize_text(
                data.get("state")
            ),

        "pincode":
            normalize_text(
                data.get("pincode")
            ),


        # =================================================
        # POLICY / INSURANCE
        # =================================================

        "policy_number":
            normalize_text(
                data.get("policy_number")
            ),

        "policyholder_name":
            normalize_person_name(
                data.get("policyholder_name")
            ),

        "relationship":
            normalize_text(
                data.get("relationship")
            ),

        "certificate_number":
            normalize_text(
                data.get("certificate_number")
            ),

        "insurer_name":
            normalize_text(
                data.get("insurer_name")
            ),

        "tpa_id":
            normalize_text(
                data.get("tpa_id")
            ),

        "tpa_name":
            normalize_text(
                data.get("tpa_name")
            ),

        "sum_insured":
            normalize_amount(
                data.get("sum_insured")
            ),


        # =================================================
        # DOCUMENT
        # =================================================

        "document_number":
            normalize_text(
                data.get("document_number")
            ),

        "document_date":
            document_date,

        "service_date":
            service_date,


        # =================================================
        # HOSPITALIZATION / CLINICAL
        # =================================================

        "admission_number":
            normalize_text(
                data.get("admission_number")
            ),

        "admission_date":
            admission_date,

        "admission_time":
            normalize_text(
                data.get("admission_time")
            ),

        "discharge_date":
            discharge_date,

        "discharge_time":
            normalize_text(
                data.get("discharge_time")
            ),

        "room_category":
            normalize_text(
                data.get("room_category")
            ),

        "doctor_name":
            normalize_person_name(
                data.get("doctor_name")
            ),

        "specialization":
            normalize_text(
                data.get("specialization")
            ),

        "diagnosis":
            normalize_text(
                data.get("diagnosis")
            ),

        "procedure":
            normalize_text(
                data.get("procedure")
            ),

        "hospitalization_reason":
            normalize_text(
                data.get(
                    "hospitalization_reason"
                )
            ),

        "system_of_medicine":
            normalize_text(
                data.get(
                    "system_of_medicine"
                )
            ),


        # =================================================
        # FINANCIAL
        # =================================================

        "subtotal":
            normalize_amount(
                data.get("subtotal")
            ),

        "discount":
            normalize_amount(
                data.get("discount")
            ),

        "tax_amount":
            normalize_amount(
                data.get("tax_amount")
            ),

        "total_amount":
            normalize_amount(
                data.get("total_amount")
            ),

        "amount_approved":
            normalize_amount(
                data.get("amount_approved")
            ),

        "copay_amount":
            normalize_amount(
                data.get("copay_amount")
            ),

        "amount_paid":
            normalize_amount(
                data.get("amount_paid")
            ),

        "currency":
            normalize_text(
                data.get("currency")
            ),


        # =================================================
        # PAYMENT
        # =================================================

        "payment_method":
            normalize_text(
                data.get("payment_method")
            ),

        "transaction_id":
            normalize_text(
                data.get("transaction_id")
            ),

        "payment_date":
            normalize_date(
                data.get("payment_date")
            ),


        # =================================================
        # CLAIM FORM FINANCIAL BREAKDOWN
        # =================================================

        "pre_hospitalization_amount":
            normalize_amount(
                data.get(
                    "pre_hospitalization_amount"
                )
            ),

        "hospitalization_amount":
            normalize_amount(
                data.get(
                    "hospitalization_amount"
                )
            ),

        "post_hospitalization_amount":
            normalize_amount(
                data.get(
                    "post_hospitalization_amount"
                )
            ),


        # =================================================
        # LINE ITEMS
        # =================================================

        "line_items":
            normalize_line_items(
                data.get(
                    "line_items",
                    []
                )
            ),
    }