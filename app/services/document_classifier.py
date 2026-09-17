import re
def get_all_text(structured_results):

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

def detect_document_type(structured_results):

    texts = get_all_text(structured_results)

    # Join all OCR text
    full_text = " ".join(texts).lower()

    # Normalize OCR whitespace
    full_text = re.sub(
        r"\s+",
        " ",
        full_text
    ).strip()

    # Compact version handles OCR such as:
    # "CLAIM  FORM", "CLAIM\nFORM", etc.
    compact_text = re.sub(
        r"[^a-z0-9]+",
        "",
        full_text
    )
    # =====================================================
    # STRONG DOCUMENT IDENTITY SIGNALS
    # =====================================================
    #
    # These identify what the document actually IS.
    # They take priority over generic words such as
    # policy, insured, claim type, payment date, etc.
    # =====================================================
    
        # =====================================================
    # EXPLICIT CLAIM FORM IDENTIFICATION
    # =====================================================

    claim_form_identity = [
        "claimform",
        "claimsreimbursementform",
        "claimreimbursementform",
        "detailsofprimaryinsured",
        "membergeneralinformation",
        "totalamountofclaim",
    ]

    identity_hits = sum(
        signal in compact_text
        for signal in claim_form_identity
    )

    if identity_hits >= 2:
        return "claim_form"

    
    strong_claim_form_signals = [
         "claim form",
    "claims form",
    "claimant",
    "details of primary insured",
    "details of insured",
    "details of hospitalization",
    "details of claim",
    "declaration by the insured",
    "claims reimbursement form",
    "claim reimbursement form",
    "member general information",
    "total amount of claim",
    "total claimed amount",
    "amount claimed",
]

    strong_invoice_signals = [
        "final bill / tax invoice",
        "tax invoice",
        "invoice no",
        "invoice number",
        "invoice date",
        "details of services & charges",
        "net payable",
    ]

    strong_receipt_signals = [
        "payment receipt",
        "official receipt",
        "receipt no",
        "receipt number",
    ]


    strong_claim_score = sum(
        signal in full_text
        for signal in strong_claim_form_signals
    )

    strong_invoice_score = sum(
        signal in full_text
        for signal in strong_invoice_signals
    )

    strong_receipt_score = sum(
        signal in full_text
        for signal in strong_receipt_signals
    )


    # =====================================================
    # PRIORITY 1 — Strong identity
    # =====================================================

    # A document explicitly identifying itself as an
    # invoice should remain an invoice even when it
    # contains policy / insurer / claim information.

    if strong_invoice_score >= 2:
        return "invoice"

    if strong_receipt_score >= 2:
        return "receipt"

    if strong_claim_score >= 2:
        return "claim_form"


    # =====================================================
    # SECONDARY SIGNALS
    # =====================================================

    claim_form_signals = [
        "claim form",
        "claims form",
        "claimant",
        "details of primary insured",
        "details of insured",
        "details of hospitalization",
        "details of claim",
        "declaration by the insured",
        "claims reimbursement form",
        "claim reimbursement form",
        "member general information",
        "total amount of claim",
    ]

    invoice_signals = [
        "invoice",
        "inpatient bill",
        "final bill",
        "bill no",
        "bill number",
        "invoice no",
        "invoice number",
        "invoice date",
        "service name",
        "particulars",
        "gross bill amount",
        "net payable",
    ]

    receipt_signals = [
        "receipt",
        "payment receipt",
        "receipt no",
        "receipt number",
        "payment method",
        "payment mode",
        "amount paid",
        "transaction id",
    ]


    claim_form_score = sum(
        signal in full_text
        for signal in claim_form_signals
    )

    invoice_score = sum(
        signal in full_text
        for signal in invoice_signals
    )

    receipt_score = sum(
        signal in full_text
        for signal in receipt_signals
    )


    # =====================================================
    # PRIORITY 2 — Highest secondary score
    # =====================================================

    scores = {
        "claim_form": claim_form_score,
        "invoice": invoice_score,
        "receipt": receipt_score,
    }

    document_type = max(
        scores,
        key=scores.get
    )

    if scores[document_type] >= 2:
        return document_type

    return "unknown"