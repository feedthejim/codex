"""Tests for rendering internal OPDS feed routes."""

from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase

from codex.views.opds.route import opds_feed_reverse


class OPDSFeedReverseTestCase(SimpleTestCase):
    """The route page must override, rather than inherit, the request page."""

    @staticmethod
    def _reverse(page: int, inherited_page: str) -> str:
        return opds_feed_reverse(
            "opds:v1:feed",
            {"collection": "folders", "pks": (42,), "page": page},
            {"topCollection": "folders", "page": inherited_page},
        )

    def test_child_first_page_drops_inherited_parent_page(self) -> None:
        """A child linked from parent page 7 starts on its own first page."""
        url = self._reverse(1, "7")

        assert urlsplit(url).path == "/opds/v1.2/folders/42"
        assert parse_qs(urlsplit(url).query) == {"topCollection": ["folders"]}

    def test_pagination_route_replaces_inherited_page(self) -> None:
        """A real pagination link keeps the page selected by its route."""
        url = self._reverse(7, "2")

        assert parse_qs(urlsplit(url).query) == {
            "topCollection": ["folders"],
            "page": ["7"],
        }
