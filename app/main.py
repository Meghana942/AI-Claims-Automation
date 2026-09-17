from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import time
from datetime import datetime
import shutil
from fastapi.middleware.cors import CORSMiddleware
from app.services.normalizer import normalize_data
from app.services.validator import validate_claim
from app.services.payload_builder import build_claim_payload
from app.services.document_parser_v3 import parse_document
from app.services.document_classifier import detect_document_type
from app.services.claim_extractor_v3 import extract_claim_fields_v3
from app.services.claim_form_extractor_v3 import extract_claim_form_fields_v3

app = FastAPI(
    title="Claims Backend",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def group_extracted_data(data):

    return {

        # -------------------------------------------------
        # Patient Details
        # -------------------------------------------------

        "patient_details": {
            "patient_name": data.get("patient_name"),
            "patient_id": data.get("patient_id"),
            "age": data.get("age"),
            "gender": data.get("gender"),
            "date_of_birth": data.get("date_of_birth"),
            "relationship": data.get("relationship"),
        },


        # -------------------------------------------------
        # Contact Details
        # -------------------------------------------------

        "contact_details": {
            "address": data.get("patient_address"),
            "city": data.get("city"),
            "state": data.get("state"),
            "pincode": data.get("pincode"),
            "phone": data.get("patient_phone"),
            "email": data.get("patient_email"),
        },


        # -------------------------------------------------
        # Policy / Insurance Details
        # -------------------------------------------------

        "policy_details": {
            "policy_number": data.get("policy_number"),
            "policyholder_name": data.get("policyholder_name"),
            "certificate_number": data.get("certificate_number"),
            "tpa_id": data.get("tpa_id"),
            "tpa_name": data.get("tpa_name"),
            "insurer_name": data.get("insurer_name"),
            "sum_insured": data.get("sum_insured"),
        },


        # -------------------------------------------------
        # Provider Details
        # -------------------------------------------------

        "provider_details": {
            "hospital_name": data.get("hospital_name"),
            "hospital_address": data.get("hospital_address"),
            "hospital_phone": data.get("hospital_phone"),
            "hospital_email": data.get("hospital_email"),
            "hospital_gstin": data.get("hospital_gstin"),
        },


        # -------------------------------------------------
        # Document Details
        # -------------------------------------------------

        "document_details": {
            "document_number": data.get("document_number"),
            "document_date": data.get("document_date"),
            "service_date": data.get("service_date"),
        },


        # -------------------------------------------------
        # Hospitalization Details
        # -------------------------------------------------

        "hospitalization_details": {
            "admission_number": data.get("admission_number"),
            "admission_date": data.get("admission_date"),
            "admission_time": data.get("admission_time"),
            "discharge_date": data.get("discharge_date"),
            "discharge_time": data.get("discharge_time"),
            "room_category": data.get("room_category"),
            "hospitalization_reason": data.get(
                "hospitalization_reason"
            ),
            "system_of_medicine": data.get(
                "system_of_medicine"
            ),
        },


        # -------------------------------------------------
        # Clinical Details
        # -------------------------------------------------

        "clinical_details": {
            "doctor_name": data.get("doctor_name"),
            "specialization": data.get("specialization"),
            "diagnosis": data.get("diagnosis"),
            "procedure": data.get("procedure"),
        },


        # -------------------------------------------------
        # Financial Details
        # -------------------------------------------------

        "financial_details": {
            "pre_hospitalization_amount": data.get(
                "pre_hospitalization_amount"
            ),
            "hospitalization_amount": data.get(
                "hospitalization_amount"
            ),
            "post_hospitalization_amount": data.get(
                "post_hospitalization_amount"
            ),
            "subtotal": data.get("subtotal"),
            "discount": data.get("discount"),
            "tax_amount": data.get("tax_amount"),
            "total_amount": data.get("total_amount"),
            "amount_approved": data.get("amount_approved"),
            "copay_amount": data.get("copay_amount"),
            "amount_paid": data.get("amount_paid"),
            "currency": data.get("currency"),
        },


        # -------------------------------------------------
        # Payment Details
        # -------------------------------------------------

        "payment_details": {
            "payment_method": data.get("payment_method"),
            "transaction_id": data.get("transaction_id"),
            "payment_date": data.get("payment_date"),
        },


        # -------------------------------------------------
        # Line Items
        # -------------------------------------------------

        "line_items": data.get("line_items", []),
    }

def generate_claim_id():

    date_part = datetime.now().strftime(
        "%Y%m%d"
    )

    unique_part = (
        uuid.uuid4()
        .hex[:8]
        .upper()
    )

    return (
        f"CLM-{date_part}-{unique_part}"
    )

def process_claim(file_path: Path):

    total_start = time.perf_counter()


    # ==================================================
    # PPSTRUCTURE
    # ==================================================

    start = time.perf_counter()

    structured_results = parse_document(
        str(file_path)
    )

    print(
        "Parser total:",
        f"{time.perf_counter() - start:.2f}s"
    )


    if not structured_results:

        return {
            "status": "failed",
            "message":
                "Unable to process the uploaded document."
        }


    # ==================================================
    # CLASSIFICATION
    # ==================================================

    start = time.perf_counter()

    document_type = detect_document_type(
        structured_results
    )

    print(
        "Classification:",
        f"{time.perf_counter() - start:.3f}s"
    )


    # ==================================================
    # EXTRACTION
    # ==================================================

    start = time.perf_counter()

    if document_type == "claim_form":

        extracted_data = (
            extract_claim_form_fields_v3(
                structured_results
            )
        )

    elif document_type in (
        "invoice",
        "receipt",
    ):

        extracted_data = (
            extract_claim_fields_v3(
                structured_results
            )
        )

    else:

        return {
            "status": "failed",
            "message":
                "Unsupported or unrecognized "
                "medical document.",
            "document_type":
                document_type
        }


    print(
        "Extraction:",
        f"{time.perf_counter() - start:.3f}s"
    )


    # ==================================================
    # NORMALIZATION
    # ==================================================

    start = time.perf_counter()

    normalized_data = normalize_data(
        extracted_data
    )

    print(
        "Normalization:",
        f"{time.perf_counter() - start:.3f}s"
    )


    # ==================================================
    # GROUPING
    # ==================================================

    start = time.perf_counter()

    grouped_data = group_extracted_data(
        normalized_data
    )

    print(
        "Grouping:",
        f"{time.perf_counter() - start:.3f}s"
    )


    # ==================================================
    # VALIDATION
    # ==================================================

    start = time.perf_counter()

    validation = validate_claim(
        normalized_data,
        document_type
    )

    print(
        "Validation:",
        f"{time.perf_counter() - start:.3f}s"
    )


    if not validation["is_valid"]:

        print(
            "TOTAL REQUEST PROCESSING:",
            f"{time.perf_counter() - total_start:.2f}s"
        )

        return {
            "status": "failed",
            "message": validation["reason"],
            "document_type": document_type,
            "extracted_data": extracted_data,
            "normalized_data": normalized_data,
            "validation": validation
        }


    # ==================================================
    # CLAIM ID
    # ==================================================

    claim_id = generate_claim_id()


    # ==================================================
    # PAYLOAD
    # ==================================================

    start = time.perf_counter()

    claim_payload = build_claim_payload(
        normalized_data,
        claim_id
    )

    print(
        "Payload:",
        f"{time.perf_counter() - start:.3f}s"
    )


    print(
        "TOTAL REQUEST PROCESSING:",
        f"{time.perf_counter() - total_start:.2f}s"
    )


    return {
        "status": "success",
        "filename": file_path.name,
        "claim_id": claim_id,
        "document_type": document_type,
        "extracted_data": grouped_data,
        "validation": validation,
        "claim_payload": claim_payload
    }

def save_upload(file: UploadFile) -> Path:

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    filename = Path(file.filename).name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Allowed formats: PDF, JPG, JPEG, PNG."
            )
        )

    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
        )

    return file_path


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "ok"
    }

@app.post("/process")
async def process_document(file: UploadFile = File(...)):

    file_path = save_upload(file)

    return process_claim(file_path)