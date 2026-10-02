import os
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from apps.accounts.models import User
from tests.test_access import assign
from tests.test_transfer_metrics import PERIOD, corrected_transfer
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db(transaction=True)


def content(response):
    assert response.status_code == 200
    return " ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)


def test_pdf_role_matrix_current_correction_and_physical_date(user):
    transfer = corrected_transfer(user)
    driver, receiver = transfer.current_version.driver, transfer.current_version.receiver
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    for actor in [user, driver, admin]:
        response = client_for(actor).get("/api/v1/reports/transfers.pdf", PERIOD)
        text = content(response)
        assert "4.000 (corregida)" in text and "2026-10-02 23:30" in text
        assert "5.000" not in text and "Corte del servidor" in text
    assert client_for(receiver).get("/api/v1/reports/transfers.pdf", PERIOD).status_code == 403
    if os.environ.get("PDF_QA_DIR"):
        (Path(os.environ["PDF_QA_DIR"]) / "transfers.pdf").write_bytes(response.content)
    for actor in [receiver, admin]:
        response = client_for(actor).get("/api/v1/reports/receptions.pdf", PERIOD)
        assert "4.000 (corregida)" in content(response)
    for actor in [user, driver]:
        assert client_for(actor).get("/api/v1/reports/receptions.pdf", PERIOD).status_code == 403
    if os.environ.get("PDF_QA_DIR"):
        (Path(os.environ["PDF_QA_DIR"]) / "receptions.pdf").write_bytes(response.content)
    empty = client_for(receiver).get(
        "/api/v1/reports/receptions.pdf", {"date_from": "2026-10-03", "date_to": "2026-10-03"}
    )
    assert "Sin registros" in content(empty)
