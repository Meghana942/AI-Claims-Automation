# AI Claims Automation

AI-powered claims automation system that extracts information from scanned claim documents, converts the extracted data into a structured format, and integrates with Oracle Health Insurance through REST APIs.

## Overview

The AI Claims Automation project streamlines the processing of healthcare claim documents by using OCR and AI-based extraction techniques. The system accepts a scanned claim document, extracts relevant claim information, structures the extracted data into a JSON payload, and prepares it for submission to Oracle Health Insurance through REST APIs.

The project includes a Python-based backend with FastAPI, OCR processing using PaddleOCR, and an Oracle APEX interface for displaying extracted claim information and API responses.

## Key Features

- Upload scanned healthcare claim documents
- Extract claim information using OCR
- Process and structure extracted data into JSON
- Validate important claim fields and extracted values
- Integrate with Oracle Health Insurance using REST APIs
- Display extracted claim information and API responses
- Oracle APEX-based user interface for claim processing

## System Workflow

1. **Upload Claim Document** – The user uploads a scanned claim document through the application.
2. **OCR Processing** – PaddleOCR processes the document and extracts relevant text and information.
3. **Data Extraction** – The extracted information is processed and mapped to the required claim fields.
4. **JSON Generation** – The extracted data is converted into a structured JSON payload.
5. **Validation** – Important claim values such as procedure details, line amounts, and total amounts are validated.
6. **OHI Integration** – The structured claim payload is sent to Oracle Health Insurance through REST APIs.
7. **Response Display** – The claim processing response is displayed through the Oracle APEX interface.

## Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn

### OCR & Document Processing

- PaddleOCR
- PP-Structure
- PaddlePaddle
- OpenCV
- PyMuPDF

### Frontend

- Oracle APEX
- JavaScript
- AJAX

### Integration

- REST APIs
- JSON
- Oracle Health Insurance (OHI)

## Project Structure

```text
AI-Claims-Automation/
│
├── app/
│   ├── main.py
│   │
│   └── services/
│       ├── claim_extractor_v3.py
│       ├── claim_form_extractor_v3.py
│       ├── document_classifier.py
│       ├── document_parser_v3.py
│       ├── normalizer.py
│       ├── payload_builder.py
│       ├── targeted_ocr.py
│       └── validator.py
│
├── uploads/
│
├── requirements.txt
├── response.json
├── test_ppstructure_v3.py
├── .gitignore
└── README.md
```

## How It Works

The system processes a claim document through the following stages:

1. **Document Upload**  
   A scanned claim document is uploaded to the backend.

2. **Document Classification**  
   The uploaded document is identified based on its type and structure.

3. **OCR & Data Extraction**  
   PaddleOCR and PP-Structure are used to detect and extract relevant information from the document.

4. **Data Normalization**  
   Extracted values are cleaned and normalized into a consistent format.

5. **Validation**  
   Important claim fields and financial values are checked for consistency.

6. **Payload Generation**  
   The processed information is converted into the JSON structure required for claim submission.

7. **API Integration**  
   The generated payload can be used with Oracle Health Insurance REST APIs for claim processing.

8. **Response Handling**  
   The API response is returned to the application and can be displayed through the Oracle APEX interface.

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Meghana942/AI-Claims-Automation.git
cd AI-Claims-Automation
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the FastAPI Application

```bash
uvicorn app.main:app --reload
```

The FastAPI server will start locally and can be accessed through the displayed local URL.

## API Documentation

Once the FastAPI application is running, the interactive API documentation can be accessed at:

```text
http://127.0.0.1:8000/docs
```

FastAPI provides an interactive Swagger UI that can be used to explore and test the available API endpoints.

## Future Enhancements

- Improve OCR accuracy for low-quality and handwritten claim documents
- Extend support for additional claim document formats
- Enhance automated validation and error handling
- Integrate additional healthcare claim workflows
- Deploy the application as a scalable cloud-based service
- Add comprehensive monitoring and logging for production environments

## Project Status

This project was developed as a prototype for automating healthcare claim processing using OCR, AI-based document extraction, structured JSON generation, and REST API integration with Oracle Health Insurance.

The current implementation demonstrates the core document processing and claim automation workflow.

## Screenshots / Demo

Screenshots demonstrating the claim document upload, extracted information, structured claim data, and application response can be added here.

> Screenshots can be added to this section to showcase the application's workflow and user interface.