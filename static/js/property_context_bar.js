/**
 * Sticky property context bar: display label, unsaved indicator, document title.
 */
(function (global) {
    function formatPropertyDisplay(data) {
        if (!data) return '';
        if (data.display) return String(data.display).trim();
        const society = data.societyname || data.society_name || data.name || '';
        const block = data.block || data.Block || '';
        const unit = data.no || data.NO || data.flat_no || '';
        const parts = [];
        if (society) parts.push(String(society).trim());
        if (block) parts.push(String(block).trim());
        if (unit) parts.push(String(unit).trim());
        return parts.join(' | ');
    }

    function captureFormSnapshot(form) {
        if (!form) return '';
        const data = Object.fromEntries(new FormData(form));
        const keys = Object.keys(data).sort();
        const normalized = {};
        keys.forEach(function (key) {
            normalized[key] = data[key] == null ? '' : String(data[key]);
        });
        return JSON.stringify(normalized);
    }

    function globalScrollToTop(e) {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault();
            e.stopPropagation();
        }
        const container = document.querySelector('.container') || document.querySelector('.form-content');
        if (container) {
            try { container.scrollTo({ top: 0, behavior: 'smooth' }); } catch (err) {}
            container.scrollTop = 0;
        }
        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (err) {}
        if (document.documentElement) document.documentElement.scrollTop = 0;
        if (document.body) document.body.scrollTop = 0;
    }

    function globalScrollToBottom(e) {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault();
            e.stopPropagation();
        }
        const container = document.querySelector('.container') || document.querySelector('.form-content');
        const targetScrollHeight = Math.max(
            container ? container.scrollHeight : 0,
            document.body ? document.body.scrollHeight : 0,
            document.documentElement ? document.documentElement.scrollHeight : 0
        );
        if (container) {
            try { container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' }); } catch (err) {}
            container.scrollTop = container.scrollHeight;
        }
        try { window.scrollTo({ top: targetScrollHeight, behavior: 'smooth' }); } catch (err) {}
        if (document.documentElement) document.documentElement.scrollTop = targetScrollHeight;
        if (document.body) document.body.scrollTop = targetScrollHeight;
    }

    // Expose functions globally for direct inline onclick or window access
    global.scrollToTop = globalScrollToTop;
    global.scrollToBottom = globalScrollToBottom;

    // Document-level event delegation (catches clicks even if elements were dynamically shown/rendered)
    document.addEventListener('click', function (e) {
        if (e.target && e.target.closest('#propertyContextTopBtn')) {
            globalScrollToTop(e);
        } else if (e.target && e.target.closest('#propertyContextBottomBtn')) {
            globalScrollToBottom(e);
        }
    }, true);

    function initPropertyContextBar(options) {
        const config = options || {};
        const form = document.querySelector(config.formSelector || 'form');
        const getSnapshot = typeof config.getFormSnapshot === 'function'
            ? function () { return config.getFormSnapshot(form); }
            : function () { return captureFormSnapshot(form); };
        const bar = document.getElementById(config.barId || 'propertyContextBar');
        const labelEl = document.getElementById(config.labelId || 'propertyContextLabel');
        const metaEl = document.getElementById(config.metaId || 'propertyContextMeta');
        const unsavedEl = document.getElementById(config.unsavedId || 'propertyContextUnsaved');
        const formTypeLabel = config.formTypeLabel || 'Form';
        const defaultTitle = config.defaultTitle || document.title;

        let cleanSnapshot = '';
        let contextState = { display: '', propertyId: '' };

        function updateUnsavedState() {
            if (!unsavedEl || !form) return;
            const dirty = cleanSnapshot && getSnapshot() !== cleanSnapshot;
            unsavedEl.hidden = !dirty;
            if (bar) {
                bar.classList.toggle('is-dirty', dirty);
            }
        }

        function updateDocumentTitle() {
            const display = contextState.display || '';
            const propertyId = contextState.propertyId || '';
            if (!display && !propertyId) {
                document.title = defaultTitle;
                return;
            }
            const shortDisplay = display.length > 48 ? display.slice(0, 45) + '...' : display;
            if (propertyId) {
                document.title = propertyId + ' · ' + shortDisplay + ' — ' + formTypeLabel;
            } else {
                document.title = shortDisplay + ' — ' + formTypeLabel;
            }
        }

        function showBar(display, propertyId) {
            contextState = {
                display: display || '',
                propertyId: propertyId != null && propertyId !== '' ? String(propertyId) : '',
            };
            if (!bar) return;

            if (labelEl) {
                labelEl.textContent = contextState.display || 'Selected property';
            }
            if (metaEl) {
                const bits = [formTypeLabel];
                if (contextState.propertyId) {
                    bits.push('ID: ' + contextState.propertyId);
                }
                metaEl.textContent = bits.join(' · ');
            }

            bar.hidden = false;
            updateDocumentTitle();
            updateUnsavedState();
        }

        function hideBar() {
            contextState = { display: '', propertyId: '' };
            cleanSnapshot = '';
            if (bar) {
                bar.hidden = true;
                bar.classList.remove('is-dirty');
            }
            if (unsavedEl) {
                unsavedEl.hidden = true;
            }
            document.title = defaultTitle;
        }

        function markClean() {
            if (form) {
                cleanSnapshot = getSnapshot();
            }
            updateUnsavedState();
        }

        function bindForm(data) {
            const display = formatPropertyDisplay(data) ||
                (document.getElementById('societySearch') || {}).value || '';
            const propertyId = (data && (data.property_id || data.propertyId)) ||
                (document.getElementById('property_id') || {}).value || '';
            showBar(display, propertyId);
            if (form) {
                cleanSnapshot = getSnapshot();
            }
            updateUnsavedState();
        }

        if (form) {
            form.addEventListener('input', updateUnsavedState);
            form.addEventListener('change', updateUnsavedState);
        }

        return {
            formatPropertyDisplay: formatPropertyDisplay,
            bindForm: bindForm,
            showBar: showBar,
            hideBar: hideBar,
            markClean: markClean,
            updateUnsavedState: updateUnsavedState,
        };
    }

    global.initPropertyContextBar = initPropertyContextBar;
})(window);
