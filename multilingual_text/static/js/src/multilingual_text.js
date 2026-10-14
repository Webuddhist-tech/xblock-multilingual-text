/* global CustomEvent */
function MultilingualTextXBlock(runtime, element) { // eslint-disable-line no-unused-vars
    'use strict';

    var root = element.querySelector ? element : element[0];
    var block = root.querySelector('.multilingual-text');
    if (!block) {
        return;
    }

    var select = block.querySelector('.multilingual-text__select');
    if (!select) {
        return;
    }

    var courseId = block.getAttribute('data-course-id');
    var storageKey = 'multilingual_text:' + courseId + ':language';
    var eventName = 'multilingual-text:language-change';
    var panels = Array.prototype.slice.call(block.querySelectorAll('.multilingual-text__content'));
    var available = panels.map(function (panel) {
        return panel.getAttribute('data-language');
    });

    function storedLanguage() {
        try {
            return window.localStorage.getItem(storageKey);
        } catch (error) {
            return null;
        }
    }

    function remember(language) {
        try {
            window.localStorage.setItem(storageKey, language);
        } catch (error) {
            // Browser privacy settings may disable localStorage; switching still works.
        }
    }

    function show(language) {
        var selected = available.indexOf(language) === -1 ? available[0] : language;
        select.value = selected;
        panels.forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-language') !== selected;
        });
        return selected;
    }

    show(storedLanguage());

    select.addEventListener('change', function () {
        var selected = show(select.value);
        remember(selected);
        window.dispatchEvent(new CustomEvent(eventName, {
            detail: {courseId: courseId, language: selected},
        }));
    });

    window.addEventListener(eventName, function (event) {
        if (event.detail && event.detail.courseId === courseId) {
            show(event.detail.language);
        }
    });
}
