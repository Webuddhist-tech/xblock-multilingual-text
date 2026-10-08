"""Tests for the Multilingual Text XBlock."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from web_fragments.fragment import Fragment
from xblock.exceptions import JsonHandlerError
from xblock.fields import ScopeIds
from xblock.test.toy_runtime import ToyRuntime

from multilingual_text import MultilingualTextXBlock


class FakeUsageKey:
    """Small usage-key stand-in for Studio synchronization tests."""

    def __init__(self, course_key, block_type, block_id):
        self.course_key = course_key
        self.context_key = course_key
        self.block_type = block_type
        self.block_id = block_id

    def replace(self, category, name):
        """Create a child key using the legacy edx-platform replace API."""
        return FakeUsageKey(self.course_key, category, name)

    def __hash__(self):
        return hash((self.course_key, self.block_type, self.block_id))

    def __eq__(self, other):
        return (
            isinstance(other, FakeUsageKey)
            and (self.course_key, self.block_type, self.block_id)
            == (other.course_key, other.block_type, other.block_id)
        )

    def __str__(self):
        return "{}:{}:{}".format(self.course_key, self.block_type, self.block_id)


def make_block(catalog=None):
    """Create a block with a mocked course-backed language catalog."""
    runtime = ToyRuntime()
    runtime.modulestore = Mock()
    runtime.modulestore.get_course.return_value = SimpleNamespace(
        other_course_settings={} if catalog is None else {"multilingual_text_languages": catalog}
    )
    location = FakeUsageKey("course-v1:Test+MT+2026", "multilingual_text", "parent")
    block = MultilingualTextXBlock(
        runtime,
        scope_ids=ScopeIds("author", "multilingual_text", "definition", location),
    )
    block.location = location
    return block


def make_child(data, content):
    """Create a rendered native Text child test double."""
    fragment = Fragment(content)
    fragment.add_css(".native-text-child { color: green; }")
    child = Mock(data=data)
    child.render.return_value = fragment
    return child


@pytest.mark.parametrize(
    "catalog,error_text",
    [
        (None, "Configure"),
        ([], "non-empty list"),
        ({"code": "en"}, "non-empty list"),
        ([123], "must be a language name or object"),
        ([""], "cannot be empty"),
        (["English", "english"], "duplicated"),
        ([{"label": "English"}, {"label": "ENGLISH"}], "duplicated"),
    ],
)
def test_invalid_catalogs(catalog, error_text):
    """Reject malformed course language catalogs with actionable errors."""
    block = make_block(catalog)

    languages, errors = block._language_catalog()

    assert languages == []
    assert error_text in " ".join(errors)


def test_catalog_accepts_language_names_and_unicode():
    """Accept simple language names directly without requiring mappings."""
    block = make_block(["English", "Tibetan", "Hindi"])
    languages, errors = block._language_catalog()
    assert errors == []
    assert languages == [
        {"code": "English", "label": "English"},
        {"code": "Tibetan", "label": "Tibetan"},
        {"code": "Hindi", "label": "Hindi"},
    ]

    block_unicode = make_block(["English", "བོད་ཡིག", "हिन्दी"])
    languages, errors = block_unicode._language_catalog()
    assert errors == []
    assert languages == [
        {"code": "English", "label": "English"},
        {"code": "བོད་ཡིག", "label": "བོད་ཡིག"},
        {"code": "हिन्दी", "label": "हिन्दी"},
    ]


def test_catalog_accepts_unicode_labels_and_language_subtags():
    """Accept Unicode labels and safe BCP-47-style language codes."""
    catalog = [
        {"code": "bo", "label": "བོད་ཡིག"},
        {"code": "pt-BR", "label": "Português"},
        {"code": "zh-Hant", "label": "繁體中文"},
    ]
    block = make_block(catalog)

    languages, errors = block._language_catalog()

    assert languages == catalog
    assert errors == []


def test_student_view_uses_catalog_order_and_excludes_unavailable_translations():
    """Render only non-empty, active translations in catalog order."""
    block = make_block([
        {"code": "bo", "label": "བོད་ཡིག"},
        {"code": "en", "label": "English <script>"},
        {"code": "hi", "label": "हिन्दी"},
    ])
    block.children = ["child-en", "child-bo", "child-hi", "child-fr"]
    block.language_blocks = {
        "en": "child-en",
        "bo": "child-bo",
        "hi": "child-hi",
        "fr": "child-fr",
    }
    children = {
        "child-bo": make_child("<p>Tibetan</p>", "<p>བོད་ཡིག content</p>"),
        "child-en": make_child("<p>English</p>", "<p>English content</p>"),
        "child-hi": make_child("", "<p>Must not render</p>"),
        "child-fr": make_child("<p>French</p>", "<p>Inactive French</p>"),
    }
    block.runtime.get_block = Mock(side_effect=children.__getitem__)

    rendered = block.student_view({}).to_dict()
    content = rendered["content"]

    assert content.index('value="bo"') < content.index('value="en"')
    assert "བོད་ཡིག content" in content
    assert "English content" in content
    assert "Must not render" not in content
    assert "Inactive French" not in content
    assert "English &lt;script&gt;" in content
    assert 'data-language="bo"' in content
    assert 'lang="bo"' in content
    assert 'dir="auto"' in content
    assert any(resource["data"] == ".native-text-child { color: green; }" for resource in rendered["resources"])


def test_student_view_shows_unavailable_message_when_all_translations_are_empty():
    """Show a useful learner message when the component has no authored content."""
    block = make_block([{"code": "en", "label": "English"}])
    block.children = ["child-en"]
    block.language_blocks = {"en": "child-en"}
    block.runtime.get_block = Mock(return_value=make_child("", ""))

    content = block.student_view({}).content

    assert "This content is not available in any language." in content
    assert "<select" not in content


def test_translation_status_preserves_inactive_and_finds_stale_mappings():
    """Separate active, missing, inactive, and deleted-child mappings."""
    block = make_block([])
    block.children = ["child-en", "child-fr"]
    block.language_blocks = {"en": "child-en", "fr": "child-fr", "de": "deleted-child"}
    catalog = [{"code": "en", "label": "English"}, {"code": "hi", "label": "हिन्दी"}]

    status = block._translation_status(catalog)

    assert status["active"] == [catalog[0]]
    assert status["missing"] == [catalog[1]]
    assert status["inactive"] == ["fr"]
    assert status["stale"] == ["de"]


def test_sync_creates_missing_renames_existing_and_is_idempotent():
    """Synchronize native Text children without duplicating existing languages."""
    block = make_block([
        {"code": "en", "label": "English"},
        {"code": "bo", "label": "བོད་ཡིག"},
    ])
    block.runtime.is_author_mode = True
    block.runtime.service = Mock(return_value=SimpleNamespace(
        get_current_user=Mock(return_value=SimpleNamespace(opt_attrs={"edx-platform.user_id": 7}))
    ))
    english_key = FakeUsageKey(block.location.course_key, "html", "english")
    block.children = [english_key]
    block.language_blocks = {"en": english_key, "deleted": "missing-child"}
    english_child = SimpleNamespace(display_name="Old English title")
    block.runtime.modulestore.get_item.return_value = english_child

    first_result = block._sync_translations()

    assert first_result["created"] == ["bo"]
    assert first_result["renamed"] == ["en"]
    assert first_result["removed_stale"] == ["deleted"]
    assert english_child.display_name == "English [en]"
    assert len(block.children) == 2
    assert block.language_blocks["bo"] == block.children[1]
    block.runtime.modulestore.create_item.assert_called_once()
    create_call = block.runtime.modulestore.create_item.call_args
    assert create_call.args[:3] == (7, block.location.course_key, "html")
    assert create_call.kwargs["metadata"] == {"display_name": "བོད་ཡིག [bo]"}

    english_child.display_name = "English [en]"
    tibetan_child = SimpleNamespace(display_name="བོད་ཡིག [bo]")
    block.runtime.modulestore.get_item.side_effect = [english_child, tibetan_child]
    second_result = block._sync_translations()

    assert second_result["created"] == []
    assert second_result["renamed"] == []
    assert len(block.children) == 2
    block.runtime.modulestore.create_item.assert_called_once()


def test_sync_preserves_languages_removed_from_catalog():
    """Keep removed-language children mapped so re-adding the code restores them."""
    block = make_block([{"code": "en", "label": "English"}])
    block.runtime.is_author_mode = True
    block.runtime.service = Mock(return_value=SimpleNamespace(
        get_current_user=Mock(return_value=SimpleNamespace(opt_attrs={"edx-platform.user_id": 7}))
    ))
    english_key = FakeUsageKey(block.location.course_key, "html", "english")
    french_key = FakeUsageKey(block.location.course_key, "html", "french")
    block.children = [english_key, french_key]
    block.language_blocks = {"en": english_key, "fr": french_key}
    block.runtime.modulestore.get_item.return_value = SimpleNamespace(display_name="English [en]")

    result = block._sync_translations()

    assert result["inactive"] == ["fr"]
    assert block.language_blocks["fr"] == french_key
    assert french_key in block.children


def test_sync_rejects_non_authors_and_invalid_catalogs_without_writes():
    """Do not mutate course content outside an authenticated Studio author request."""
    block = make_block(None)

    with pytest.raises(JsonHandlerError) as non_author_error:
        block._sync_translations()
    assert non_author_error.value.status_code == 403

    block.runtime.is_author_mode = True
    block.runtime.service = Mock(return_value=SimpleNamespace(
        get_current_user=Mock(return_value=SimpleNamespace(opt_attrs={"edx-platform.user_id": 7}))
    ))
    with pytest.raises(JsonHandlerError) as catalog_error:
        block._sync_translations()
    assert catalog_error.value.status_code == 400
    block.runtime.modulestore.create_item.assert_not_called()
    block.runtime.modulestore.update_item.assert_not_called()
