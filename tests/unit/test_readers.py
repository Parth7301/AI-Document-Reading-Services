"""
tests/unit/test_readers.py
Unit tests for all document reader post-processing logic.
"""
import pytest
from app.services.readers.aadhaar_reader import AadhaarReader
from app.services.readers.pan_reader import PANReader
from app.services.readers.marksheet_reader import MarksheetReader
from app.services.readers.tc_reader import TCReader
from app.services.validators.expiry_validator import ExpiryValidatorService, DocumentStatus


# ── Aadhaar Tests ─────────────────────────────────────────────────────────────

class TestAadhaarReader:
    def setup_method(self):
        self.reader = AadhaarReader()

    def test_valid_aadhaar_format(self):
        data = {"aadhaar_number": "234567891234", "gender": "male", "address": {}}
        result = self.reader.post_process(data)
        assert result["aadhaar_number"] == "2345 6789 1234"
        assert result["is_valid_format"] is True

    def test_invalid_aadhaar_format(self):
        data = {"aadhaar_number": "12345", "gender": "female", "address": {}}
        result = self.reader.post_process(data)
        assert result["is_valid_format"] is False

    def test_gender_normalization(self):
        reader = AadhaarReader()
        assert reader.post_process({"gender": "male", "address": {}})["gender"] == "Male"
        assert reader.post_process({"gender": "FEMALE", "address": {}})["gender"] == "Female"

    def test_address_full_construction(self):
        data = {
            "aadhaar_number": "123456789012",
            "gender": "Male",
            "address": {
                "house": "12A", "street": "MG Road",
                "village_town": "Pune", "district": "Pune",
                "state": "Maharashtra", "pincode": "411001"
            }
        }
        result = self.reader.post_process(data)
        assert "MG Road" in result.get("address_full", "")
        assert "Maharashtra" in result.get("address_full", "")


# ── PAN Tests ─────────────────────────────────────────────────────────────────

class TestPANReader:
    def setup_method(self):
        self.reader = PANReader()

    def test_valid_pan(self):
        data = {"pan_number": "ABCDE1234F", "name": "john doe", "fathers_name": "james doe"}
        result = self.reader.post_process(data)
        assert result["is_valid_pan"] is True
        assert result["name"] == "John Doe"

    def test_invalid_pan(self):
        data = {"pan_number": "INVALID", "name": "Test"}
        result = self.reader.post_process(data)
        assert result["is_valid_pan"] is False

    def test_pan_type_detection(self):
        data = {"pan_number": "ABCPE1234F", "name": "Test"}
        result = self.reader.post_process(data)
        assert result.get("pan_holder_type") == "Individual (Person)"

    def test_pan_company_type(self):
        data = {"pan_number": "ABCCE1234F", "name": "Test Corp"}
        result = self.reader.post_process(data)
        assert result.get("pan_holder_type") == "Company"


# ── Marksheet Tests ───────────────────────────────────────────────────────────

class TestMarksheetReader:
    def setup_method(self):
        self.reader = MarksheetReader()

    def test_percentage_computation(self):
        data = {
            "student_name": "ram kumar",
            "subjects": [
                {"subject_name": "Maths", "total_obtained": 85, "total_max": 100, "result": "PASS"},
                {"subject_name": "Science", "total_obtained": 78, "total_max": 100, "result": "PASS"},
                {"subject_name": "English", "total_obtained": 72, "total_max": 100, "result": "PASS"},
                {"subject_name": "Hindi", "total_obtained": 65, "total_max": 100, "result": "PASS"},
                {"subject_name": "Social", "total_obtained": 70, "total_max": 100, "result": "PASS"},
            ],
        }
        result = self.reader.post_process(data)
        assert result["total_marks_obtained"] == 370
        assert result["percentage_computed"] == 74.0
        assert result["subjects_passed"] == 5
        assert result["division"] == "First Division"
        assert result["student_name"] == "Ram Kumar"

    def test_distinction_division(self):
        data = {
            "percentage": 82.5,
            "subjects": [],
        }
        result = self.reader.post_process(data)
        assert result["division"] == "Distinction"

    def test_best_of_5_computed(self):
        data = {
            "subjects": [
                {"total_obtained": 90, "total_max": 100, "result": "PASS"},
                {"total_obtained": 80, "total_max": 100, "result": "PASS"},
                {"total_obtained": 70, "total_max": 100, "result": "PASS"},
                {"total_obtained": 60, "total_max": 100, "result": "PASS"},
                {"total_obtained": 50, "total_max": 100, "result": "PASS"},
                {"total_obtained": 40, "total_max": 100, "result": "PASS"},  # 6th subject excluded
            ],
        }
        result = self.reader.post_process(data)
        assert result.get("best_of_5_percentage") == 70.0  # (90+80+70+60+50)/5


# ── Expiry Validator Tests ────────────────────────────────────────────────────

class TestExpiryValidator:
    def setup_method(self):
        self.service = ExpiryValidatorService()

    def test_parse_date_dd_mm_yyyy(self):
        from datetime import date
        result = self.service._parse_date("15/08/2023")
        assert result == date(2023, 8, 15)

    def test_parse_date_invalid(self):
        result = self.service._parse_date("not a date")
        assert result is None

    def test_parse_date_none(self):
        result = self.service._parse_date(None)
        assert result is None

    def test_expired_status(self):
        from datetime import date, timedelta
        today = date.today()
        past_date = today - timedelta(days=400)
        status, days_rem, days_exp = self.service._compute_status(past_date, past_date - timedelta(days=765))
        assert status == DocumentStatus.EXPIRED
        assert days_exp == 400

    def test_valid_status(self):
        from datetime import date, timedelta
        today = date.today()
        future_date = today + timedelta(days=180)
        status, days_rem, days_exp = self.service._compute_status(future_date, today)
        assert status == DocumentStatus.VALID
        assert days_rem == 180

    def test_expiring_soon(self):
        from datetime import date, timedelta
        today = date.today()
        soon = today + timedelta(days=15)
        status, days_rem, _ = self.service._compute_status(soon, today)
        assert status == DocumentStatus.EXPIRING_SOON
        assert days_rem == 15

    def test_no_expiry(self):
        from datetime import date
        status, _, _ = self.service._compute_status(None, date(2020, 1, 1))
        assert status == DocumentStatus.NO_EXPIRY

    def test_validity_rules_available(self):
        rules = self.service.get_all_validity_rules()
        assert "income_certificate" in rules
        assert "domicile_certificate" in rules
        assert "ews_certificate" in rules
