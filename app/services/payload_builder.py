def remove_empty_values(value):
    """
    Recursively remove values that should not be sent
    in the final claim payload.

    Removes:
    - None
    - empty strings
    - empty dictionaries
    - empty lists

    Keeps:
    - 0
    - 0.0
    - False
    """

    if isinstance(value, dict):

        cleaned = {}

        for key, item in value.items():

            cleaned_item = remove_empty_values(
                item
            )

            if cleaned_item is None:
                continue

            if cleaned_item == "":
                continue

            if cleaned_item == {}:
                continue

            if cleaned_item == []:
                continue

            cleaned[key] = cleaned_item

        return cleaned


    if isinstance(value, list):

        cleaned_list = []

        for item in value:

            cleaned_item = remove_empty_values(
                item
            )

            if cleaned_item is None:
                continue

            if cleaned_item == "":
                continue

            if cleaned_item == {}:
                continue

            if cleaned_item == []:
                continue

            cleaned_list.append(
                cleaned_item
            )

        return cleaned_list


    return value


def build_claim_payload(
    data,
    claim_id=None
):
    """
    Build the final business claim payload from
    normalized extraction data.

    The payload is intentionally richer than the
    original minimal payload.

    Optional unavailable fields are removed
    recursively before returning.
    """

    payload = {
        # ==================================================
        # CLAIM
        # ==================================================
        
        "claimId": claim_id,

        "claimType": "MEDICAL",

        "status": "NEW",

        "currency": data.get(
            "currency"
        ),


        # ==================================================
        # PATIENT
        # ==================================================

        "patientDetails": {

            "patientName":
                data.get("patient_name"),

            "patientId":
                data.get("patient_id"),

            "age":
                data.get("age"),

            "gender":
                data.get("gender"),

            "dateOfBirth":
                data.get("date_of_birth"),

            "relationship":
                data.get("relationship"),
        },


        # ==================================================
        # PATIENT CONTACT
        # ==================================================

        "contactDetails": {

            "address":
                data.get("patient_address"),

            "city":
                data.get("city"),

            "state":
                data.get("state"),

            "pincode":
                data.get("pincode"),

            "phone":
                data.get("patient_phone"),

            "email":
                data.get("patient_email"),
        },


        # ==================================================
        # POLICY / INSURANCE
        # ==================================================

        "policyDetails": {

            "policyNumber":
                data.get("policy_number"),

            "policyholderName":
                data.get("policyholder_name"),

            "memberId":
                data.get("member_id"),

            "certificateNumber":
                data.get("certificate_number"),

            "tpaId":
                data.get("tpa_id"),

            "tpaName":
                data.get("tpa_name"),

            "insurerName":
                data.get("insurer_name"),

            "sumInsured":
                data.get("sum_insured"),
        },


        # ==================================================
        # PROVIDER
        # ==================================================

        "providerDetails": {

            "hospitalName":
                data.get("hospital_name"),

            "hospitalAddress":
                data.get("hospital_address"),

            "hospitalPhone":
                data.get("hospital_phone"),

            "hospitalEmail":
                data.get("hospital_email"),

            "hospitalGstin":
                data.get("hospital_gstin"),
        },


        # ==================================================
        # DOCUMENT
        # ==================================================

        "documentDetails": {

            "documentNumber":
                data.get("document_number"),

            "documentDate":
                data.get("document_date"),

            "serviceDate":
                data.get("service_date"),
        },


        # ==================================================
        # HOSPITALIZATION
        # ==================================================

        "hospitalizationDetails": {

            "admissionNumber":
                data.get("admission_number"),

            "admissionDate":
                data.get("admission_date"),

            "admissionTime":
                data.get("admission_time"),

            "dischargeDate":
                data.get("discharge_date"),

            "dischargeTime":
                data.get("discharge_time"),

            "roomCategory":
                data.get("room_category"),

            "hospitalizationReason":
                data.get(
                    "hospitalization_reason"
                ),

            "systemOfMedicine":
                data.get(
                    "system_of_medicine"
                ),
        },


        # ==================================================
        # CLINICAL
        # ==================================================

        "clinicalDetails": {

            "doctorName":
                data.get("doctor_name"),

            "specialization":
                data.get("specialization"),

            "diagnosis":
                data.get("diagnosis"),

            "procedure":
                data.get("procedure"),
        },


        # ==================================================
        # FINANCIAL
        # ==================================================

        "financialDetails": {

            "preHospitalizationAmount":
                data.get(
                    "pre_hospitalization_amount"
                ),

            "hospitalizationAmount":
                data.get(
                    "hospitalization_amount"
                ),

            "postHospitalizationAmount":
                data.get(
                    "post_hospitalization_amount"
                ),

            "subtotal":
                data.get("subtotal"),

            "discount":
                data.get("discount"),

            "taxAmount":
                data.get("tax_amount"),

            "claimAmount":
                data.get("total_amount"),

            "amountApproved":
                data.get("amount_approved"),

            "copayAmount":
                data.get("copay_amount"),

            "amountPaid":
                data.get("amount_paid"),
        },


        # ==================================================
        # PAYMENT
        # ==================================================

        "paymentDetails": {

            "paymentMethod":
                data.get("payment_method"),

            "transactionId":
                data.get("transaction_id"),

            "paymentDate":
                data.get("payment_date"),
        },


        # ==================================================
        # CLAIM LINES
        # ==================================================

        "claimLines":
            data.get("line_items") or [],
    }


    # Remove all unavailable optional values.
    return remove_empty_values(
        payload
    )