"""Tests for metadata normalization during import aggregation."""

from decimal import Decimal

import pytest

from codex.librarian.scribe.importer.read.aggregate_path import (
    AggregateMetadataImporter,
)


@pytest.mark.parametrize("number", [0, Decimal()])
def test_transform_metadata_preserves_issue_number_zero(number) -> None:
    """Issue zero is a valid number and must survive normalization."""
    metadata = {"issue": {"number": number}}

    AggregateMetadataImporter._transform_metadata(metadata)  # noqa: SLF001

    assert metadata == {"issue_number": number}


@pytest.mark.parametrize("number", [None, ""])
def test_transform_metadata_ignores_empty_issue_number(number) -> None:
    """Missing issue numbers must not become imported field values."""
    metadata = {"issue": {"number": number}}

    AggregateMetadataImporter._transform_metadata(metadata)  # noqa: SLF001

    assert metadata == {}
