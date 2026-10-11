import React, { useEffect, useState } from 'react';

import { SitesPage } from './pages/SitesPage.jsx';
import { SitePlanPage } from './pages/SitePlanPage.jsx';
import { BacktestPage } from './pages/BacktestPage.jsx';
import { MethodPage } from './pages/MethodPage.jsx';

import { DISCLAIMER_TEXT } from './utils.js';
import { getHealth, isMockMode } from './api.js';

function resolveRoute(hash) {
    const path = (hash || '#/')
        .replace(/^#/, '')
        .split('?')[0];

    const segments = path.split('/').filter(Boolean);

    if (segments.length === 0) return { page: 'sites' };

    if (segments[0] === 'site' && segments[1]) {
        try {
            return {
                page: 'site',
                siteId: decodeURIComponent(segments[1]),
            };
        } catch {
            return { page: 'not-found' };
        }
    }

    if (segments[0] === 'backtest') return { page: 'backtest' };
    if (segments[0] === 'method') return { page: 'method' };

    return { page: 'not-found' };
}

function NavIcon({ type }) {
    const common = {
        width: 21,
        height: 21,
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: 1.8,
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        'aria-hidden': true,
    };

    switch (type) {
        case 'sites':
            return (
                <svg {...common}>
                    <rect x="3.5" y="3.5" width="7" height="7" rx="2" />
                    <rect x="13.5" y="3.5" width="7" height="7" rx="2" />
                    <rect x="3.5" y="13.5" width="7" height="7" rx="2" />
                    <rect x="13.5" y="13.5" width="7" height="7" rx="2" />
                </svg>
            );

        case 'backtest':
            return (
                <svg {...common}>
                    <path d="M3 3v18h18" />
                    <rect x="6" y="12" width="3.5" height="6" rx="1" />
                    <rect x="11.5" y="8" width="3.5" height="10" rx="1" />
                    <rect x="17" y="4" width="3.5" height="14" rx="1" />
                </svg>
            );

        case 'method':
            return (
                <svg {...common}>
                    <path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H20v17H7.5A2.5 2.5 0 0 0 5 21.5z" />
                    <path d="M5 4.5v17M9 7h7M9 11h7" />
                </svg>
            );

        default:
            return null;
    }
}

function ShieldMark() {
    return (
        <svg
            width="25"
            height="25"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <path d="M12 2.5 20 5.5v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10v-6z" />
            <path d="m8.5 12 2.3 2.3 4.8-5" />
        </svg>
    );
}

function App() {
    const [hash, setHash] = useState(
        () => window.location.hash || '#/'
    );

    const [language, setLanguage] = useState('en');
    const [systemStatus, setSystemStatus] = useState({ loading: true, online: false });

    useEffect(() => {
        function handleHashChange() {
            setHash(window.location.hash || '#/');
        }

        window.addEventListener('hashchange', handleHashChange);
        return () => {
            window.removeEventListener('hashchange', handleHashChange);
        };
    }, []);

    useEffect(() => {
        let active = true;
        getHealth()
            .then((health) => {
                if (active) setSystemStatus({ loading: false, online: Boolean(health.ok), version: health.version });
            })
            .catch(() => {
                if (active) setSystemStatus({ loading: false, online: false });
            });
        return () => { active = false; };
    }, []);

    const route = resolveRoute(hash);
    const isSitesActive = route.page === 'sites' || route.page === 'site';

    let page;

    switch (route.page) {
        case 'sites':
            page = <SitesPage />;
            break;

        case 'site':
            page = (
                <SitePlanPage
                    siteId={route.siteId}
                    language={language}
                />
            );
            break;

        case 'backtest':
            page = <BacktestPage />;
            break;

        case 'method':
            page = <MethodPage />;
            break;

        default:
            page = (
                <section className="error-card" role="status">
                    <h1 className="error-title">Page not found</h1>
                    <p className="error-msg">
                        This page is not available in the current dashboard stage.
                    </p>
                    <a className="return-link" href="#/">
                        Return to Sites
                    </a>
                </section>
            );
    }

    return (
        <div className="app-container dashboard-app">
            <aside className="sidebar">
                <a
                    href="#/"
                    className="sidebar-brand"
                    aria-label="ShramShield home"
                >
                    <span className="brand-icon">
                        <ShieldMark />
                    </span>

                    <span className="brand-copy">
                        <strong className="brand-name">ShramShield</strong>
                        <span className="brand-caption">HEAT SAFETY</span>
                    </span>
                </a>

                <div className="sidebar-divider" />

                <div className="sidebar-section-label">
                    WORKSPACE
                </div>

                <nav className="sidebar-nav" aria-label="Primary navigation">
                    <a
                        href="#/"
                        className={`sidebar-link ${isSitesActive ? 'active' : ''}`}
                        aria-current={isSitesActive ? 'page' : undefined}
                    >
                        <span className="sidebar-link-icon">
                            <NavIcon type="sites" />
                        </span>
                        <span>Sites</span>
                    </a>

                    <a
                        href="#/backtest"
                        className={`sidebar-link ${route.page === 'backtest' ? 'active' : ''}`}
                        aria-current={route.page === 'backtest' ? 'page' : undefined}
                    >
                        <span className="sidebar-link-icon">
                            <NavIcon type="backtest" />
                        </span>
                        <span>Backtest</span>
                    </a>

                    <a
                        href="#/method"
                        className={`sidebar-link ${route.page === 'method' ? 'active' : ''}`}
                        aria-current={route.page === 'method' ? 'page' : undefined}
                    >
                        <span className="sidebar-link-icon">
                            <NavIcon type="method" />
                        </span>
                        <span>Method</span>
                    </a>
                </nav>

                <div className="sidebar-bottom">
                    <div className="sidebar-sun" aria-hidden="true">
                        <svg
                            width="25"
                            height="25"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                        >
                            <circle cx="12" cy="12" r="4" />
                            <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
                        </svg>
                    </div>
                    <strong>Heat awareness</strong>
                    <p>Weather-based screening for outdoor worksites.</p>
                </div>
            </aside>

            <div className="dashboard-main-column">
                <header className="topbar">
                    <div className="topbar-context">
                        <span className="topbar-eyebrow">
                            SHRAMSHIELD / OPERATIONS
                        </span>
                        <span className="topbar-caption">
                            Worksite heat safety dashboard
                        </span>
                    </div>

                    <div
                        className="language-control"
                        role="group"
                        aria-label="Message language"
                    >
                        <span className="language-label">Message language</span>

                        <button
                            type="button"
                            className={`language-option ${language === 'en' ? 'active' : ''}`}
                            aria-pressed={language === 'en'}
                            onClick={() => setLanguage('en')}
                        >
                            EN
                        </button>

                        <button
                            type="button"
                            className={`language-option ${language === 'hi' ? 'active' : ''}`}
                            aria-pressed={language === 'hi'}
                            onClick={() => setLanguage('hi')}
                        >
                            HI
                        </button>
                    </div>
                </header>

                <main id="main-content" className="dashboard-content">
                    {page}
                </main>

                <footer className="dashboard-footer">
                    <div className="disclaimer-box">
                        <strong>Important safety notice</strong>
                        <p>{DISCLAIMER_TEXT}</p>
                    </div>

                    <p className="footer-brand">
                        ShramShield <span aria-hidden="true">·</span> Heat Safety Operations
                    </p>
                    <p className="system-status" role="status">
                        System status: {systemStatus.loading
                            ? 'Checking API…'
                            : systemStatus.online
                                ? (isMockMode ? 'Fixture mode' : `API online, v${systemStatus.version}`)
                                : 'API unreachable'}
                    </p>
                </footer>
            </div>
        </div>
    );
}

export default App;
