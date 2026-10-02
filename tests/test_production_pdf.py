import os
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from apps.accounts.models import User
from apps.reports.pdf import deny_fetch
from tests.test_milk_metrics import PERIOD, confirmed
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db(transaction=True)


def test_production_pdf_real_content_scope_cutoff_and_filters(user):
    confirmed(user)
    client = client_for(user)
    response = client.get("/api/v1/reports/production.pdf", PERIOD)
    assert response.status_code == 200
    assert (
        response["Content-Type"] == "application/pdf"
        and response["Cache-Control"] == "private, no-store"
    )
    pdf = PdfReader(BytesIO(response.content))
    text = " ".join(page.extract_text() for page in pdf.pages)
    assert "3.000" in text and "V0" in text and "2026-10-01" in text
    assert "Sin registro" not in text and "sincronizados" in text and "Corte del servidor" in text
    assert pdf.pages[0].mediabox.width == pytest.approx(595.28, abs=1)
    if os.environ.get("PDF_QA_DIR"):
        path = Path(os.environ["PDF_QA_DIR"])
        path.mkdir(parents=True, exist_ok=True)
        (path / "production.pdf").write_bytes(response.content)
    outsider = User.objects.create_user(username="outsider")
    assert client_for(outsider).get("/api/v1/reports/production.pdf", PERIOD).status_code == 403
    empty = client.get(
        "/api/v1/reports/production.pdf", {"date_from": "2026-09-01", "date_to": "2026-09-02"}
    )
    assert "Sin registros" in " ".join(
        page.extract_text() for page in PdfReader(BytesIO(empty.content)).pages
    )
    assert client.get("/api/v1/reports/production.pdf", {}).status_code == 422


def test_report_fetcher_blocks_network_and_local_files():
    for url in ["https://example.org/private", "file:///etc/passwd", "data:text/plain,secret"]:
        with pytest.raises(ValueError):
            deny_fetch(url)


def test_pdf_pagination_repeated_headers_and_escaped_text(user):
    from datetime import date

    from django.utils import timezone

    from apps.reports.pdf import render_pdf

    data = {"date_from": date(2026, 10, 1), "date_to": date(2026, 10, 3), "cutoff": timezone.now()}
    section = {
        "title": "Detalle",
        "text": "Texto controlado",
        "headers": ["Vaca", "Litros"],
        "rows": [[f"V{i:03d}", "2.000"] for i in range(100)],
    }
    section["rows"][0][0] = '<img src="file:///private">'
    response = render_pdf("Informe de prueba", data, {}, [section], "test")
    pdf = PdfReader(BytesIO(response.content))
    assert len(pdf.pages) >= 3
    for page in pdf.pages:
        assert "Vaca" in page.extract_text()
    assert '<img src="file:///private">' in pdf.pages[0].extract_text()
    assert "V099" in pdf.pages[-1].extract_text()
    if os.environ.get("PDF_QA_DIR"):
        (Path(os.environ["PDF_QA_DIR"]) / "production-long.pdf").write_bytes(response.content)
