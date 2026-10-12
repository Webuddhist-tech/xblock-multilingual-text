Multilingual Text XBlock
########################

``multilingual_text`` is an Open edX container XBlock that presents the same
Text content in multiple languages. Each translation is a native Open edX Text
(``html``) child, so course authors keep the standard rich-text editor, source
editor, links, tables, images, and course asset workflow.

Learners choose a language from a dropdown above the content. Their choice is
remembered in the browser for the current course and is shared by other
Multilingual Text blocks on the same page.

Platform setup
**************

Install this package in both the LMS and CMS Open edX images. For a published
package or Git repository, add it to Tutor's
``OPENEDX_EXTRA_PIP_REQUIREMENTS`` and rebuild the Open edX image.

Studio must expose the **Other Course Settings** field. Enable it with a small
Tutor plugin containing this patch:

.. code-block:: python

    from tutor import hooks

    hooks.Filters.ENV_PATCHES.add_item((
        "openedx-cms-common-settings",
        "ENABLE_OTHER_COURSE_SETTINGS = True",
    ))

Run ``tutor config save`` and restart or rebuild the platform after enabling
the plugin. This is a one-time platform change; editing course languages later
does not require a deployment.

Course setup
************

In **Studio > Settings > Advanced Settings**:

1. Add ``multilingual_text`` to **Advanced Module List**.
2. Set **Other Course Settings** to an object containing an ordered language
   catalog:

   .. code-block:: json

       {
         "multilingual_text_languages": ["English", "Tibetan", "Hindi"]
       }

   Native script names can also be used directly:

   .. code-block:: json

       {
         "multilingual_text_languages": ["English", "བོད་ཡིག", "हिन्दी"]
       }

Language names can be any custom Unicode text without needing ISO language codes or mappings. Catalog order controls the initial default language presented to the learner.

Authoring translations
**********************

1. Add **Multilingual Text** from Advanced Components.
2. Select **View** to open its container page.
3. Select **Create missing components**.
4. Edit each generated Text child with the normal Open edX Text editor.
5. Publish the changed course content.

Only languages with non-empty content appear to learners. Removing a language
from the course catalog hides it from learners but preserves its Text child and
content. Re-adding the same code restores it. Use **Refresh components**
after changing labels or adding languages.

Development and testing
***********************

Install the development requirements and run the complete test suite:

.. code-block:: bash

    make requirements
    tox

The XBlock SDK Workbench can render the package shell, but it does not provide
Open edX's course settings or mutable Studio modulestore. Translation creation
must therefore be integration-tested in Tutor/Open edX.

To run Workbench in Docker:

.. code-block:: bash

    make dev.run

Workbench is then available at http://localhost:8000.

Scope and limitations
*********************

Version 1 supports responsive LMS web pages. It does not provide machine
translation, grading, account-level preference synchronization, a dedicated
language settings page, Content Library authoring, or native mobile app UI.
