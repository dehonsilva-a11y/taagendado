/* ==========================================================================
   DESIGN SYSTEM LELLO · APP.JS INTERATIVIDADE
   Tema (Claro / Bordô), Sidebar Mobile, Modais Nativos e Acessibilidade
   ========================================================================== */

(function () {
    'use strict';

    // ----------------------------------------------------------------------
    // 1. GERENCIAMENTO DE TEMA (CLARO / BORDÔ)
    // ----------------------------------------------------------------------
    const STORAGE_KEY = 'lello-theme';

    function getTheme() {
        return localStorage.getItem(STORAGE_KEY) || document.documentElement.getAttribute('data-theme') || 'claro';
    }

    function setTheme(theme) {
        const root = document.documentElement;
        root.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);

        // Atualiza botões de tema na interface
        document.querySelectorAll('.lo-theme-btn').forEach(btn => {
            const isMatch = btn.getAttribute('data-theme-set') === theme;
            btn.setAttribute('aria-pressed', isMatch ? 'true' : 'false');
        });
    }

    // Inicializa botões de tema
    function initTheme() {
        const current = getTheme();
        setTheme(current);

        document.querySelectorAll('.lo-theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTheme = btn.getAttribute('data-theme-set');
                if (targetTheme) {
                    setTheme(targetTheme);
                }
            });
        });
    }

    // ----------------------------------------------------------------------
    // 2. CONTROLE DA SIDEBAR RESPONSIVA (MOBILE)
    // ----------------------------------------------------------------------
    function initSidebar() {
        const sidebar = document.getElementById('lelloSidebar');
        const overlay = document.getElementById('lelloOverlay');
        const toggles = document.querySelectorAll('[data-sidebar-toggle]');

        if (!sidebar) return;

        function openSidebar() {
            sidebar.classList.add('is-open');
            if (overlay) overlay.classList.add('is-visible');
            document.body.style.overflow = 'hidden';
        }

        function closeSidebar() {
            sidebar.classList.remove('is-open');
            if (overlay) overlay.classList.remove('is-visible');
            document.body.style.overflow = '';
        }

        toggles.forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                if (sidebar.classList.contains('is-open')) {
                    closeSidebar();
                } else {
                    openSidebar();
                }
            });
        });

        if (overlay) {
            overlay.addEventListener('click', closeSidebar);
        }

        // Fecha ao pressionar ESC
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
                closeSidebar();
            }
        });

        // Fecha se a tela expandir para desktop
        window.addEventListener('resize', () => {
            if (window.innerWidth >= 992 && sidebar.classList.contains('is-open')) {
                closeSidebar();
            }
        });
    }

    // ----------------------------------------------------------------------
    // 3. SISTEMA DE MODAIS NATIVO DO DESIGN SYSTEM
    // ----------------------------------------------------------------------
    window.openLoModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('is-active');
        document.body.style.overflow = 'hidden';

        // Auto foco no primeiro campo editável
        const firstInput = modal.querySelector('input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 80);
        }
    };

    window.closeLoModal = function (modalId) {
        const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
        if (!modal) return;
        modal.classList.remove('is-active');
        if (!document.querySelector('.lo-modal-overlay.is-active')) {
            document.body.style.overflow = '';
        }
    };

    function initModals() {
        // Gatilhos de abertura [data-lo-modal-target="idDoModal"]
        document.querySelectorAll('[data-lo-modal-target]').forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = trigger.getAttribute('data-lo-modal-target');
                if (targetId) window.openLoModal(targetId);
            });
        });

        // Gatilhos de fechamento [data-lo-modal-close]
        document.querySelectorAll('[data-lo-modal-close]').forEach(closeBtn => {
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const modal = closeBtn.closest('.lo-modal-overlay');
                if (modal) window.closeLoModal(modal);
            });
        });

        // Fecha ao clicar no backdrop (fora do .lo-modal)
        document.querySelectorAll('.lo-modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    window.closeLoModal(overlay);
                }
            });
        });

        // Fecha modais com ESC
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const activeModal = document.querySelector('.lo-modal-overlay.is-active');
                if (activeModal) {
                    window.closeLoModal(activeModal);
                }
            }
        });

        // Polyfill suave para qualquer chamada de bootstrap.Modal legado
        window.bootstrap = window.bootstrap || {};
        window.bootstrap.Modal = function (el) {
            this.el = typeof el === 'string' ? document.querySelector(el) : el;
            this.show = function () {
                if (this.el) {
                    this.el.classList.add('is-active');
                    this.el.style.display = 'grid';
                    document.body.style.overflow = 'hidden';
                }
            };
            this.hide = function () {
                if (this.el) {
                    this.el.classList.remove('is-active');
                    this.el.style.display = '';
                    document.body.style.overflow = '';
                }
            };
        };
    }

    // ----------------------------------------------------------------------
    // 4. UTILITÁRIOS DE FORMULÁRIO E FEEDBACK
    // ----------------------------------------------------------------------
    function initFormUtils() {
        // Previne clique duplo em formulários
        document.querySelectorAll('form[data-once]').forEach(form => {
            form.addEventListener('submit', () => {
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.7';
                });
            });
        });

        // Auto-dispensa de avisos temporários após 8 segundos
        setTimeout(() => {
            document.querySelectorAll('.lo-callout[data-auto-dismiss]').forEach(alert => {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-8px)';
                setTimeout(() => alert.remove(), 420);
            });
        }, 8000);
    }

    // ----------------------------------------------------------------------
    // INICIALIZAÇÃO NO DOM READY
    // ----------------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initTheme();
            initSidebar();
            initModals();
            initFormUtils();
        });
    } else {
        initTheme();
        initSidebar();
        initModals();
        initFormUtils();
    }
})();