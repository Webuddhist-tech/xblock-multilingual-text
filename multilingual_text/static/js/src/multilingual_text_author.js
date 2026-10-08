function MultilingualTextAuthorXBlock(runtime, element) {
    'use strict';

    var root = element.querySelector ? element : element[0];
    var button = root.querySelector('[data-sync-translations]');
    var result = root.querySelector('[data-sync-result]');
    if (!button) {
        return;
    }

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
        return match ? decodeURIComponent(match[3]) : null;
    }

    button.addEventListener('click', function () {
        button.disabled = true;
        result.textContent = button.getAttribute('data-syncing-message');

        var csrfToken = getCookie('csrftoken') || getCookie('edx_csrf_token') || window.csrf_token || window.CSRF_TOKEN;
        var headers = {'Content-Type': 'application/json'};
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        fetch(runtime.handlerUrl(element, 'sync_translations'), {
            method: 'POST',
            credentials: 'same-origin',
            headers: headers,
            body: '{}',
        }).then(function (response) {
            if (!response.ok) {
                return response.text().then(function (text) {
                    var message;
                    try {
                        var body = JSON.parse(text);
                        message = body.error || body.message;
                    } catch (e) {
                        // Response is HTML or non-JSON text
                    }
                    throw new Error(message || button.getAttribute('data-error-message') + ' (HTTP ' + response.status + ')');
                });
            }
            return response.json();
        }).then(function () {
            window.location.reload();
        }).catch(function (error) {
            result.textContent = error.message;
            button.disabled = false;
        });
    });
}
