# 📄 Document Reading Services — AI-Powered System

Production-grade document processing system using **Google Gemini Free API** + **OCR** for Indian government documents.

## 🏗️ Architecture Overview

```
doc-reader-system/
├── app/
│   ├── api/v1/endpoints/        # FastAPI route handlers
│   ├── core/                    # Config, security, logging
│   ├── models/                  # DB models (SQLAlchemy)
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/
│   │   ├── readers/             # Document-specific readers
│   │   └── validators/          # Expiry & validation logic
│   └── utils/                   # OCR, Gemini client, helpers
├── tests/
├── config/
├── scripts/
└── docs/
```

## 🚀 Quick Start

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # Add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

## 📚 Supported Documents

| Service           | Document             | Extracted Fields                          |
| ----------------- | -------------------- | ----------------------------------------- |
| Aadhaar Reader    | Aadhaar Card         | Name, DOB, Gender, Address, Aadhaar No.   |
| PAN Reader        | PAN Card             | PAN No., Name, DOB, Father's Name         |
| Board Certificate | SSC/HSC/Diploma      | Student Name, School, Board, Year, Result |
| TC Reader         | Transfer Certificate | Name, Admission No., DOB, Leaving Date    |
| Marksheet Reader  | 10th/12th Marksheets | Subjects, Marks, Percentage, Grade        |
| Expiry Checker    | Income/Domicile Cert | Issue Date, Expiry Date, Valid/Expired    |

## 🔑 Environment Variables

```
GEMINI_API_KEY=your_key_here
TESSERACT_PATH=/usr/bin/tesseract
MAX_FILE_SIZE_MB=10
ALLOWED_FORMATS=jpg,jpeg,png,pdf
```
