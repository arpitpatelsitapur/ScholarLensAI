// ScholarLens AI - Main JavaScript File

document.addEventListener('DOMContentLoaded', function() {
    initNavbar();
    initScrollToTop();
    highlightActiveNavLink();
    initTableTabs();
    initPaperTableRows();
    initDashboardFilters();
    styleSourceButtons();
    // NEW → Equalize bookmarks if the page has them
    if (document.querySelector('.bookmark-card')) {
        equalizeBookmarkCards();
        setTimeout(equalizeBookmarkCards, 300); // handle late font rendering
    }
});

// Initialize FAQ accordion on the homepage (not all pages have it)
function initFaqAccordion() {
    const faqList = document.querySelector('.faq-list');
    if (!faqList) return;

    faqList.querySelectorAll('.faq-item').forEach(item => {
        item.classList.remove('open');
        const q = item.querySelector('.faq-question');
        if (q) q.setAttribute('aria-expanded', 'false');
    });

    faqList.addEventListener('click', function(e) {
        const btn = e.target.closest('.faq-question');
        if (!btn) return;
        const item = btn.closest('.faq-item');
        if (!item) return;

        const expanded = btn.getAttribute('aria-expanded') === 'true';

        if (!expanded) {
            faqList.querySelectorAll('.faq-item.open').forEach(openItem => {
                if (openItem === item) return;
                openItem.classList.remove('open');
                const q = openItem.querySelector('.faq-question');
                if (q) q.setAttribute('aria-expanded', 'false');
                const a = openItem.querySelector('.faq-answer');
                if (a) a.style.maxHeight = null;
            });
        }

        btn.setAttribute('aria-expanded', String(!expanded));
        item.classList.toggle('open', !expanded);

        const answer = item.querySelector('.faq-answer');
        if (answer) {
            if (!expanded) answer.style.maxHeight = answer.scrollHeight + 'px';
            else answer.style.maxHeight = null;
        }
    });
}

// Navbar functionality
function initNavbar() {
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');
    const rightSection = document.querySelector('.right-section');

    if (!hamburger) return;
    hamburger.setAttribute('aria-expanded', 'false');

    hamburger.addEventListener('click', function() {
        if (navLinks) navLinks.classList.toggle('active');
        if (rightSection) rightSection.classList.toggle('active');
        const expanded = navLinks && navLinks.classList.contains('active');
        hamburger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    });
}

// Highlight active nav link based on current page
function highlightActiveNavLink() {
    const currentPage = window.location.pathname.split('/').pop();
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        const linkPage = link.getAttribute('href');
        if (currentPage === linkPage || (currentPage === '' && linkPage === 'index.html')) {
            link.classList.add('active');
        }
    });
}

// Scroll to top button
function initScrollToTop() {
    const scrollTopBtn = document.querySelector('.scroll-top');
    if (!scrollTopBtn) return;

    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) scrollTopBtn.classList.add('visible');
        else scrollTopBtn.classList.remove('visible');
    });

    scrollTopBtn.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// table tab handler 
function initTableTabs() {
    try {
        const tabsContainer = document.querySelector('.table-tabs');
        const panels = document.querySelectorAll('.table-panel');
        if (!tabsContainer) {
            console.debug('initTableTabs: .table-tabs container not found');
            return;
        }

        // Provide accessible attributes on tabs if missing
        tabsContainer.querySelectorAll('.table-tab').forEach((t, i) => {
            if (!t.hasAttribute('role')) t.setAttribute('role', 'tab');
            if (!t.hasAttribute('aria-selected')) t.setAttribute('aria-selected', t.classList.contains('active') ? 'true' : 'false');
            if (!t.hasAttribute('tabindex')) t.setAttribute('tabindex', '0');
        });

        tabsContainer.addEventListener('click', function(e) {
            const tab = e.target.closest('.table-tab');
            if (!tab) return;

            const target = tab.getAttribute('data-target');
            if (!target) {
                console.debug('initTableTabs: clicked .table-tab without data-target', tab);
                return;
            }

            const tabs = tabsContainer.querySelectorAll('.table-tab');
            tabs.forEach(t => {
                const isActive = (t === tab);
                t.classList.toggle('active', isActive);
                t.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });

            let found = false;
            panels.forEach(panel => {
                if (panel.getAttribute('data-panel') === target) {
                    panel.classList.add('active');
                    found = true;
                    // Reinitialize paper row handlers for the newly active panel
                    initPaperTableRows();
                } else {
                    panel.classList.remove('active');
                }
            });

            if (!found) console.debug('initTableTabs: no .table-panel matched', target);
        });

        // Keyboard support: allow Enter/Space to activate focused tab
        tabsContainer.addEventListener('keydown', function(e) {
            const tab = e.target.closest('.table-tab');
            if (!tab) return;
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                tab.click();
            }
        });

        // Default open: try to open the tab marked active, or fall back to data-target="new"
        const activeTab = tabsContainer.querySelector('.table-tab.active');
        const defaultTab = activeTab || tabsContainer.querySelector('.table-tab[data-target="new"]');
        if (defaultTab) defaultTab.click();

    } catch (err) {
        console.error('initTableTabs failed:', err);
    }
}

// Initialize paper table row expansion and handle bookmarks
function initPaperTableRows() {
    const activePanel = document.querySelector('.table-panel.active');
    if (!activePanel) return;

    // Ensure all abstracts are collapsed on init
    activePanel.querySelectorAll('.abstract-row').forEach(ar => ar.classList.remove('show'));
    activePanel.querySelectorAll('.paper-row').forEach(row => row.classList.remove('expanded'));

    activePanel.querySelectorAll('.paper-row').forEach(row => {
        // Use delegated click on row itself
        row.addEventListener('click', function() {
            const paperId = this.getAttribute('data-paper-id') || this.dataset.paperId;
            const abstractRow = document.getElementById(`abstract-${paperId}`);
            if (!abstractRow) return;

            // Close other abstracts
            activePanel.querySelectorAll('.abstract-row.show').forEach(openRow => {
                if (openRow !== abstractRow) {
                    openRow.classList.remove('show');
                    if (openRow.previousElementSibling) openRow.previousElementSibling.classList.remove('expanded');
                }
            });

            abstractRow.classList.toggle('show');
            this.classList.toggle('expanded');
        });
    });

    // Prevent clicks on buttons from triggering row expansion
    activePanel.querySelectorAll('.action-btn, .source-button').forEach(button => {
        button.addEventListener('click', (e) => e.stopPropagation());
    });
}

// Dashboard filters stub (safe no-op if not present)
function initDashboardFilters() {
    // Placeholder: keep for pages that may add JS-driven filters later
    const filterArea = document.querySelector('.dashboard-filters');
    if (!filterArea) return;
}

// Source button styling
function styleSourceButtons() {
    document.querySelectorAll('.source-button').forEach(btn => {
        const src = btn.textContent.trim().toLowerCase();
        if (src.includes('arxiv')) btn.classList.add('arxiv');
        else if (src.includes('ieee')) btn.classList.add('ieee');
        else if (src.includes('anthropic')) btn.classList.add('anthropic');
        else if (src.includes('free')) btn.classList.add('free');
        else if (src.includes('not')) btn.classList.add('notfree');
        else btn.classList.add('others');
    });
}

function equalizeBookmarkCards() {
    const cards = document.querySelectorAll('.bookmark-card');
    if (!cards.length) return;

    // Reset heights first
    cards.forEach(card => card.style.height = 'auto');

    // Find max height
    let maxH = 0;
    cards.forEach(card => {
        const h = card.getBoundingClientRect().height;
        if (h > maxH) maxH = h;
    });

    // Apply max height
    cards.forEach(card => {
        card.style.height = maxH + 'px';
    });
}


// Chat with paper functionality (opens PDF/chat in new tab)
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('chat-btn')) {
        e.preventDefault();
        const href = e.target.getAttribute('href');
        if (href && href !== '#') window.open(href, '_blank');
        else showToast('Chat/PDF not available for this paper', 'error');
    }
});

// Toast notification
function showToast(message, type = 'success') {
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
///////////////////////////
// Toggle filter box
///////////////////////////
const filterBox = document.querySelector(".filter-box");
const filterHeader = document.querySelector(".filter-header");
const filterContent = document.querySelector(".filter-content");

filterHeader.addEventListener("click", () => {
    filterBox.classList.toggle("active");

    if (filterContent.style.display === "block") {
        filterContent.style.display = "none";
    } else {
        filterContent.style.display = "block";
    }
});

// Show category input OR topic input depending on selection
const filterType = document.getElementById("filter-type");
const categoryBox = document.getElementById("category-box");
const topicBox = document.getElementById("topic-box");

filterType.addEventListener("change", () => {
    const type = filterType.value;

    if (type === "category") {
        categoryBox.classList.remove("hidden");
        topicBox.classList.add("hidden");
    } else if (type === "topic") {
        topicBox.classList.remove("hidden");
        categoryBox.classList.add("hidden");
    } else {
        categoryBox.classList.add("hidden");
        topicBox.classList.add("hidden");
    }
});

// Submit button handler (frontend only for now)
document.getElementById("filter-submit").addEventListener("click", () => {
    const type = filterType.value;

    if (type === "category") {
        const category = document.getElementById("category-select").value;
        if (!category) return alert("Please select a category.");
        alert("Searching papers by category: " + category);
    }

    if (type === "topic") {
        const topic = document.getElementById("topic-input").value.trim();
        if (!topic) return alert("Please enter a topic.");
        alert("Searching papers by topic: " + topic);
    }

    // Later backend call will be done here (fetch or redirect)
});


window.addEventListener('resize', function() {
    if (document.querySelector('.bookmark-card')) {
        equalizeBookmarkCards();
    }
});



