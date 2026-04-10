(function () {
    const SESSION_STORAGE_KEY = 'tableau_freezer_audit_session_id';

    function safe(callable, fallback) {
        try {
            return callable();
        } catch (_err) {
            return fallback;
        }
    }

    function getSessionId() {
        let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
        if (!sessionId) {
            sessionId = (window.crypto && crypto.randomUUID)
                ? crypto.randomUUID()
                : 'sess_' + Date.now() + '_' + Math.random().toString(16).slice(2);
            localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        }
        return sessionId;
    }

    function newEventId() {
        return (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : 'evt_' + Date.now() + '_' + Math.random().toString(16).slice(2);
    }

    async function getUserAgentHints() {
        const uaData = safe(() => navigator.userAgentData, null);
        if (!uaData) {
            return null;
        }

        const basic = {
            brands: uaData.brands,
            mobile: uaData.mobile,
            platform: uaData.platform,
        };

        if (!uaData.getHighEntropyValues) {
            return basic;
        }

        try {
            const high = await uaData.getHighEntropyValues([
                'platformVersion',
                'architecture',
                'model',
                'uaFullVersion',
                'bitness',
                'fullVersionList',
            ]);
            return Object.assign({}, basic, high);
        } catch (_err) {
            return basic;
        }
    }

    function buildClientContextBase() {
        const connection = safe(() => navigator.connection, null);
        return {
            client_timestamp_utc: new Date().toISOString(),
            page_url: window.location.href,
            user_agent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            languages: navigator.languages,
            cookie_enabled: navigator.cookieEnabled,
            timezone: safe(() => Intl.DateTimeFormat().resolvedOptions().timeZone, null),
            timezone_offset_minutes: new Date().getTimezoneOffset(),
            screen: {
                width: safe(() => window.screen.width, null),
                height: safe(() => window.screen.height, null),
                avail_width: safe(() => window.screen.availWidth, null),
                avail_height: safe(() => window.screen.availHeight, null),
                color_depth: safe(() => window.screen.colorDepth, null),
                pixel_ratio: window.devicePixelRatio || 1,
            },
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight,
            },
            hardware_concurrency: safe(() => navigator.hardwareConcurrency, null),
            device_memory_gb: safe(() => navigator.deviceMemory, null),
            max_touch_points: safe(() => navigator.maxTouchPoints, null),
            online: navigator.onLine,
            network_effective_type: safe(() => connection && connection.effectiveType, null),
            network_downlink_mbps: safe(() => connection && connection.downlink, null),
            network_rtt_ms: safe(() => connection && connection.rtt, null),
            network_save_data: safe(() => connection && connection.saveData, null),
            do_not_track: navigator.doNotTrack,
        };
    }

    async function getPublicIpCandidate() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1500);
        try {
            const response = await fetch('https://api64.ipify.org?format=json', {
                method: 'GET',
                signal: controller.signal,
            });
            if (!response.ok) {
                return null;
            }
            const data = await response.json();
            return data.ip || null;
        } catch (_err) {
            return null;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    async function buildClientContext() {
        const base = buildClientContextBase();
        const uaHints = await getUserAgentHints();
        const publicIpCandidate = await getPublicIpCandidate();
        return Object.assign({}, base, {
            user_agent_hints: uaHints,
            public_ip_candidate: publicIpCandidate,
        });
    }

    async function sendWhoAmI(baseUrl, payload) {
        const eventType = (payload && payload.event_type) || 'context_event';
        const data = {
            user: payload && payload.user ? payload.user : null,
            dashboard: payload && payload.dashboard ? payload.dashboard : null,
            session_id: payload && payload.session_id ? payload.session_id : getSessionId(),
            event_id: payload && payload.event_id ? payload.event_id : newEventId(),
            event_type: eventType,
            client_context: await buildClientContext(),
        };

        return fetch(baseUrl + '/audit/user-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    window.UserContextCollector = {
        getSessionId: getSessionId,
        sendWhoAmI: sendWhoAmI,
    };
})();
