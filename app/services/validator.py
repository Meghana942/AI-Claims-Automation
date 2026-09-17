def validate_claim(data, document_type):

    if document_type == "claim_form":
        required_fields = [
            "patient_name",
            "hospital_name",
            "service_date",
            "total_amount",
        ]

    else:
        required_fields = [
            "patient_name",
            "document_number",
            "service_date",
            "total_amount",
        ]

    missing_fields = [
        field
        for field in required_fields
        if data.get(field) in (None, "", [])
    ]

    total_amount = data.get("total_amount")

    amount_valid = (
        isinstance(total_amount, (int, float))
        and total_amount > 0
    )

    is_valid = (
        len(missing_fields) == 0
        and amount_valid
    )

    return {
        "is_valid": is_valid,
        "reason": (
            "Valid medical claim document."
            if is_valid
            else "Required claim fields are missing."
        ),
        "missing_fields": missing_fields,
        "amount_valid": amount_valid,
        "normalized_total_amount": total_amount,
    }