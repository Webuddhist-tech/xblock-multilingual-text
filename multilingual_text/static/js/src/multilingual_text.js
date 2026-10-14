/* global CustomEvent */
function MultilingualTextXBlock(runtime, element) { // eslint-disable-line no-unused-vars
    'use strict';

    var root = element.querySelector ? element : element[0];
    var block = root.querySelector('.multilingual-text');
    if (!block) {
        return;
    }

    var dropdown = block.querySelector('.multilingual-text__dropdown');
    if (!dropdown) {
        return;
    }

    var trigger = dropdown.querySelector('.multilingual-text__trigger');
    var triggerValue = dropdown.querySelector('.multilingual-text__value');
    var listbox = dropdown.querySelector('.multilingual-text__options');
    var options = Array.prototype.slice.call(dropdown.querySelectorAll('.multilingual-text__option'));
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
        options.forEach(function (option) {
            var isSelected = option.getAttribute('data-language-option') === selected;
            option.setAttribute('aria-selected', isSelected ? 'true' : 'false');
            option.classList.toggle('multilingual-text__option--selected', isSelected);
            if (isSelected) {
                triggerValue.textContent = option.textContent;
            }
        });
        panels.forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-language') !== selected;
        });
        return selected;
    }

    function closeDropdown(returnFocus) {
        listbox.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        if (returnFocus) {
            trigger.focus();
        }
    }

    function openDropdown() {
        listbox.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        (options.find(function (option) {
            return option.getAttribute('aria-selected') === 'true';
        }) || options[0]).focus();
    }

    function choose(language) {
        var selected = show(language);
        remember(selected);
        window.dispatchEvent(new CustomEvent(eventName, {
            detail: {courseId: courseId, language: selected},
        }));
    }

    show(storedLanguage());

    trigger.addEventListener('click', function () {
        if (listbox.hidden) {
            openDropdown();
        } else {
            closeDropdown(true);
        }
    });

    options.forEach(function (option) {
        option.addEventListener('click', function () {
            choose(option.getAttribute('data-language-option'));
            closeDropdown(true);
        });
    });

    listbox.addEventListener('keydown', function (event) {
        var index = options.indexOf(document.activeElement);
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            index = event.key === 'ArrowDown'
                ? (index + 1) % options.length
                : (index - 1 + options.length) % options.length;
            options[index].focus();
        } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            options[event.key === 'Home' ? 0 : options.length - 1].focus();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            closeDropdown(true);
        } else if (event.key === 'Tab') {
            closeDropdown(false);
        }
    });

    trigger.addEventListener('keydown', function (event) {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            openDropdown();
        }
    });

    document.addEventListener('click', function (event) {
        if (!dropdown.contains(event.target)) {
            closeDropdown(false);
        }
    });

    window.addEventListener(eventName, function (event) {
        if (event.detail && event.detail.courseId === courseId) {
            show(event.detail.language);
        }
    });
}
