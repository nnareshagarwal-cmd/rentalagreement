/**
 * Safekeys shared browser utilities (escapeHtml, toasts, navbar, fetch).
 */
(function (global) {
    'use strict';

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function showMessage(text, type, elementId) {
        const id = elementId || 'message';
        const messageEl = document.getElementById(id);
        if (!messageEl) {
            console.warn('Safekeys.showMessage: element not found:', id);
            return;
        }
        messageEl.textContent = text;
        messageEl.className = 'message ' + type + ' show';
        window.clearTimeout(messageEl._safekeysHideTimer);
        messageEl._safekeysHideTimer = window.setTimeout(function () {
            messageEl.classList.remove('show');
        }, 4000);
    }

    function initNavbar() {
        const navMenu = document.getElementById('navMenu');
        const menuToggle = document.getElementById('menuToggle');
        if (!navMenu || !menuToggle) {
            return;
        }

        const dropdowns = document.querySelectorAll('.nav-dropdown');

        menuToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            const open = navMenu.classList.toggle('open');
            menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (!open) {
                dropdowns.forEach(function (d) {
                    d.classList.remove('open');
                    const trigger = d.querySelector('.nav-trigger');
                    if (trigger) {
                        trigger.setAttribute('aria-expanded', 'false');
                    }
                });
            }
        });

        dropdowns.forEach(function (dropdown) {
            const trigger = dropdown.querySelector('.nav-trigger');
            if (!trigger) {
                return;
            }
            trigger.addEventListener('click', function (e) {
                e.stopPropagation();
                const willOpen = !dropdown.classList.contains('open');
                dropdowns.forEach(function (d) {
                    d.classList.remove('open');
                    const t = d.querySelector('.nav-trigger');
                    if (t) {
                        t.setAttribute('aria-expanded', 'false');
                    }
                });
                if (willOpen) {
                    dropdown.classList.add('open');
                    trigger.setAttribute('aria-expanded', 'true');
                }
            });
        });

        document.addEventListener('click', function () {
            dropdowns.forEach(function (d) {
                d.classList.remove('open');
                const trigger = d.querySelector('.nav-trigger');
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'false');
                }
            });
            navMenu.classList.remove('open');
            menuToggle.setAttribute('aria-expanded', 'false');
        });

        navMenu.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            const message = result && (result.error || result.message) ? (result.error || result.message) : 'Request failed';
            throw new Error(message);
        }
        return result;
    }

    const Safekeys = {
        escapeHtml: escapeHtml,
        showMessage: showMessage,
        initNavbar: initNavbar,
        fetchJson: fetchJson,
    };

    global.Safekeys = Safekeys;
    global.escapeHtml = escapeHtml;
    global.showMessage = showMessage;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavbar);
    } else {
        initNavbar();
    }
})(typeof window !== 'undefined' ? window : this);
