"""Multilingual Text XBlock."""

import hashlib
import os
import re
from importlib import import_module
from uuid import uuid4

from django.utils.translation import gettext_noop as _
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError, NoSuchServiceError
from xblock.fields import ReferenceValueDict, Scope, String
from xblock.utils.resources import ResourceLoader
from xblock.utils.studio_editable import StudioContainerXBlockMixin, StudioEditableXBlockMixin

resource_loader = ResourceLoader(__name__)

CATALOG_SETTING = "multilingual_text_languages"
USER_ID_ATTRIBUTE = "edx-platform.user_id"


def _platform_modulestore():
    """Return Open edX's modulestore when running inside Studio."""
    try:
        return import_module("xmodule.modulestore.django").modulestore()
    except ImportError:
        return None


@XBlock.needs("i18n")
@XBlock.needs("mako")
@XBlock.needs("user")
class MultilingualTextXBlock(StudioEditableXBlockMixin, StudioContainerXBlockMixin, XBlock):
    """Display author-created Text blocks in a learner-selectable language."""

    has_children = True
    has_score = False

    display_name = String(
        display_name=_("Display Name"),
        help=_("The name of this component in Studio."),
        default=_("Multilingual Text"),
        scope=Scope.settings,
    )
    language_blocks = ReferenceValueDict(
        help=_("Maps configured language codes to their native Text child blocks."),
        scope=Scope.content,
    )

    editable_fields = ("display_name",)

    def resource_string(self, path):
        """Return a bundled text resource."""
        return resource_loader.load_unicode(os.path.join("static", path))

    def _i18n_service(self):
        """Return the runtime translation service when one is available."""
        try:
            return self.runtime.service(self, "i18n")
        except NoSuchServiceError:
            return None

    @property
    def course_key(self):
        """Return the course key for this block."""
        usage_id = self.scope_ids.usage_id
        return getattr(usage_id, "context_key", getattr(usage_id, "course_key", None))

    def _language_catalog(self):
        """Return the validated course language catalog and any validation errors."""
        runtime_store = getattr(self.runtime, "modulestore", None)
        if runtime_store is None or not hasattr(runtime_store, "get_course"):
            runtime_store = _platform_modulestore()

        if runtime_store is None or not hasattr(runtime_store, "get_course"):
            return [], [_('The course language catalog is unavailable in this runtime.')]

        course = runtime_store.get_course(self.course_key)
        course_settings = getattr(course, "other_course_settings", None) or {}
        raw_catalog = course_settings.get(CATALOG_SETTING)

        if raw_catalog is None:
            return [], [_('Configure "multilingual_text_languages" in Other Course Settings.')]
        if not isinstance(raw_catalog, list) or not raw_catalog:
            return [], [_('The multilingual text language catalog must be a non-empty list.')]

        catalog = []
        errors = []
        seen_codes = set()
        for position, language in enumerate(raw_catalog, start=1):
            if isinstance(language, str):
                name = language.strip()
                code = name
                label = name
            elif isinstance(language, dict):
                code = language.get("code") or language.get("label") or language.get("name") or ""
                label = language.get("label") or language.get("name") or code
                code = code.strip() if isinstance(code, str) else ""
                label = label.strip() if isinstance(label, str) else ""
            else:
                errors.append(_("Language entry %(position)s must be a language name or object.") % {"position": position})
                continue

            if not label:
                errors.append(_("Language entry %(position)s cannot be empty.") % {"position": position})
                continue

            if len(label) > 100:
                errors.append(
                    _("Language entry %(position)s is too long (maximum 100 characters).")
                    % {"position": position}
                )
                continue

            normalized_code = code.casefold()
            if normalized_code in seen_codes:
                errors.append(_("Language %(name)s is duplicated.") % {"name": label})
                continue

            seen_codes.add(normalized_code)
            catalog.append({"code": code, "label": label})

        return (catalog if not errors else []), errors

    def _translation_status(self, catalog):
        """Describe active, missing, inactive, and stale translation mappings."""
        child_ids = set(self.children)
        mapping = dict(self.language_blocks)
        active_codes = {language["code"] for language in catalog}
        missing = [
            language for language in catalog
            if language["code"] not in mapping or mapping[language["code"]] not in child_ids
        ]
        active = [language for language in catalog if language not in missing]
        inactive = [code for code, child_id in mapping.items() if code not in active_codes and child_id in child_ids]
        stale = [code for code, child_id in mapping.items() if child_id not in child_ids]
        return {
            "active": active,
            "missing": missing,
            "inactive": inactive,
            "stale": stale,
        }

    def student_view(self, context=None):
        """Render the learner language selector and all available translations."""
        catalog, _errors = self._language_catalog()
        child_ids = set(self.children)
        translations = []
        fragment = Fragment()

        for language in catalog:
            child_id = self.language_blocks.get(language["code"])
            if child_id not in child_ids:
                continue
            child = self.runtime.get_block(child_id)
            if not getattr(child, "data", "").strip():
                continue

            child_fragment = child.render("student_view", context or {})
            fragment.add_fragment_resources(child_fragment)
            translations.append({
                "code": language["code"],
                "label": language["label"],
                "content": child_fragment.content,
            })

        usage_id = str(self.scope_ids.usage_id)
        element_id = "multilingual-text-{}".format(
            hashlib.sha256(usage_id.encode("utf-8")).hexdigest()[:12]
        )
        fragment.add_content(resource_loader.render_django_template(
            "static/html/multilingual_text.html",
            {
                "course_id": str(self.course_key),
                "element_id": element_id,
                "translations": translations,
            },
            i18n_service=self._i18n_service(),
        ))
        fragment.add_css(self.resource_string("css/multilingual_text.css"))
        fragment.add_javascript(self.resource_string("js/src/multilingual_text.js"))
        fragment.initialize_js("MultilingualTextXBlock")
        return fragment

    def author_edit_view(self, context):
        """Render translation status and native Text children in Studio."""
        catalog, errors = self._language_catalog()
        status = self._translation_status(catalog) if not errors else {
            "active": [], "missing": [], "inactive": [], "stale": [],
        }

        fragment = Fragment(resource_loader.render_django_template(
            "static/html/multilingual_text_author.html",
            {
                "catalog_errors": errors,
                "catalog": catalog,
                "status": status,
            },
            i18n_service=self._i18n_service(),
        ))
        fragment.add_css(self.resource_string("css/multilingual_text.css"))
        if not errors:
            fragment.add_javascript(self.resource_string("js/src/multilingual_text_author.js"))
            fragment.initialize_js("MultilingualTextAuthorXBlock")
        self.render_children(context, fragment, can_reorder=False, can_add=False)
        return fragment

    def _current_author_id(self):
        """Return the current Studio author's numeric user ID."""
        if not getattr(self.runtime, "is_author_mode", False):
            raise JsonHandlerError(403, _("Translation synchronization is available only in Studio."))

        user_service = self.runtime.service(self, "user")
        current_user = user_service.get_current_user()
        user_id = current_user.opt_attrs.get(USER_ID_ATTRIBUTE)
        if user_id is None:
            raise JsonHandlerError(403, _("The current Studio user could not be identified."))
        return user_id

    def _sync_translations(self):
        """Create missing Text children and refresh managed child titles."""
        user_id = self._current_author_id()
        catalog, errors = self._language_catalog()
        if errors:
            raise JsonHandlerError(400, " ".join(errors))

        store = getattr(self.runtime, "modulestore", None)
        if store is None or not all(hasattr(store, method) for method in ("create_item", "get_item", "update_item")):
            store = _platform_modulestore()

        if store is None or not all(hasattr(store, method) for method in ("create_item", "get_item", "update_item")):
            raise JsonHandlerError(500, _("A mutable Studio modulestore is required."))

        child_ids = set(self.children)
        removed_stale = []
        for code, child_id in list(self.language_blocks.items()):
            if child_id not in child_ids:
                del self.language_blocks[code]
                removed_stale.append(code)

        created = []
        renamed = []
        for language in catalog:
            code = language["code"]
            label = language["label"]
            title = label if code == label else "{} [{}]".format(label, code)
            child_id = self.language_blocks.get(code)
            if child_id is None:
                child_id = self.scope_ids.usage_id.replace(category="html", name=uuid4().hex)
                store.create_item(
                    user_id,
                    self.course_key,
                    child_id.block_type,
                    block_id=child_id.block_id,
                    definition_data="",
                    metadata={"display_name": title},
                    runtime=self.runtime,
                )
                self.children.append(child_id)
                self.language_blocks[code] = child_id
                created.append(code)
                continue

            child = store.get_item(child_id)
            if child.display_name != title:
                child.display_name = title
                store.update_item(child, user_id)
                renamed.append(code)

        if created or removed_stale:
            store.update_item(self, user_id)

        active_codes = {language["code"] for language in catalog}
        inactive = [code for code in self.language_blocks if code not in active_codes]
        return {
            "created": created,
            "renamed": renamed,
            "inactive": inactive,
            "removed_stale": removed_stale,
        }

    @XBlock.json_handler
    def sync_translations(self, _data, suffix=""):
        """Synchronize child Text blocks with the current course catalog."""
        del suffix
        return self._sync_translations()

    @staticmethod
    def workbench_scenarios():
        """Provide a basic Workbench rendering scenario."""
        return [("Multilingual Text", "<multilingual_text />")]
