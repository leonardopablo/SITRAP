from pathlib import Path

import yaml
from drf_spectacular.generators import SchemaGenerator


def test_committed_openapi_matches_implemented_routes():
    actual = SchemaGenerator().get_schema(request=None, public=True)
    expected = yaml.safe_load(Path("docs/openapi.yaml").read_text(encoding="utf-8"))
    assert actual == expected, "Regenerate docs/openapi.yaml before committing API changes."
