import os
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from apps.accounts.models import User
from tests.test_access import assign
from tests.test_transfer_metrics import PERIOD, corrected_transfer
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db(transaction=True)


def test_overview_admin_only_filters_shared_snapshot_and_real_pdf(user):
    transfer = corrected_transfer(user)
    for actor in [user, transfer.current_version.driver, transfer.current_version.receiver]:
        for path in ["metrics/overview", "reports/overview.pdf"]:
            assert client_for(actor).get("/api/v1/" + path, PERIOD).status_code == 403
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    client = client_for(admin)
    data = client.get("/api/v1/metrics/overview", PERIOD).json()
    assert data["production"]["liters"] == "5.500"
    assert data["transfers"]["picked_up_liters"] == data["transfers"]["received_liters"] == "4.000"
    assert data["cutoff"] == data["production"]["cutoff"] == data["transfers"]["cutoff"]
    assert data["centers"][0]["produced_liters"] == "5.500"
    assert (
        client.get("/api/v1/metrics/overview", {**PERIOD, "product_id": uuid.uuid4()}).json()[
            "centers"
        ]
        == []
    )
    assert (
        client.get(
            "/api/v1/metrics/overview", {**PERIOD, "center_id": transfer.current_version.origin_id}
        ).json()["centers"]
        == data["centers"]
    )
    response = client.get("/api/v1/reports/overview.pdf", PERIOD)
    assert response.status_code == 200
    text = " ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert "Resumen administrativo" in text and "5.500" in text and "4.000 (corregida)" in text
    if os.environ.get("PDF_QA_DIR"):
        (Path(os.environ["PDF_QA_DIR"]) / "overview.pdf").write_bytes(response.content)
