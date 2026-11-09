let currencyOptions = [];
let destinationsByCurrency = {};
let activeModal = null;
let csrfToken = "";
let quoteRequest = 0;

class APIError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function ensureCsrfToken() {
    if (csrfToken) return csrfToken;

    const response = await fetch("/api/csrf/", { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || !data.csrfToken) {
        throw new APIError("Impossible d'initialiser la session sécurisée.", response.status);
    }
    csrfToken = data.csrfToken;
    return csrfToken;
}

async function apiRequest(url, options = {}) {
    const method = options.method || "GET";
    const headers = { Accept: "application/json" };
    if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
    }
    if (method !== "GET" && method !== "HEAD") {
        headers["X-CSRFToken"] = await ensureCsrfToken();
    }

    const response = await fetch(url, {
        ...options,
        method,
        headers: { ...headers, ...options.headers },
        credentials: "same-origin",
    });
    const data = await response.json();
    if (!response.ok) {
        if (response.status === 403) csrfToken = "";
        throw new APIError(data.error || "La requête n'a pas abouti.", response.status);
    }
    return data;
}

function showFeedback(elementId, message, isError = true) {
    const feedback = document.getElementById(elementId);
    if (!feedback) return;
    feedback.textContent = message;
    feedback.classList.toggle("hidden", !message);
    feedback.classList.toggle("form-feedback--error", isError);
    feedback.classList.toggle("form-feedback--success", !isError);
}

function formatCurrency(value, currency) {
    const amount = Number(value);
    return `${amount.toLocaleString("fr-FR", {
        maximumFractionDigits: ["XAF", "XOF", "CDF", "NGN"].includes(currency) ? 0 : 2,
    })} ${currency}`;
}

function buildCurrencyLabel(code) {
    const currency = currencyOptions.find(option => option.code === code);
    return currency ? `${code} - ${currency.name}` : code;
}

async function initializeCurrencySelectors() {
    const data = await apiRequest("/api/transfers/currencies/");
    currencyOptions = data.currencies;
    destinationsByCurrency = data.destinations;

    const sourceSelect = document.getElementById("source-country");
    sourceSelect.innerHTML = Object.keys(destinationsByCurrency)
        .sort()
        .map(code => `<option value="${code}">${buildCurrencyLabel(code)}</option>`)
        .join("");
    sourceSelect.value = "EUR";
    updateDestinationOptions();
}

function updateDestinationOptions() {
    const sourceCurrency = document.getElementById("source-country").value;
    const destinationSelect = document.getElementById("dest-country");
    const destinations = destinationsByCurrency[sourceCurrency] || [];

    destinationSelect.innerHTML = destinations
        .map(code => `<option value="${code}">${buildCurrencyLabel(code)}</option>`)
        .join("");
    if (destinations.length) {
        destinationSelect.value = destinations.includes("XAF") ? "XAF" : destinations[0];
    }
    calculate();
}

function updateComplianceInfo(sourceCurrency, destinationCurrency) {
    const info = document.getElementById("compliance-info");
    if (sourceCurrency !== "XOF" && destinationCurrency !== "XOF") {
        info.classList.add("hidden");
        return;
    }

    document.getElementById("compliance-details").textContent =
        "Les transferts impliquant le franc CFA BCEAO sont soumis aux contrôles réglementaires applicables.";
    info.classList.remove("hidden");
}

async function calculate() {
    const sourceCurrency = document.getElementById("source-country").value;
    const destinationCurrency = document.getElementById("dest-country").value;
    const amount = document.getElementById("amount").value;
    const requestId = ++quoteRequest;

    document.getElementById("amount-label").textContent =
        `Montant à envoyer (${sourceCurrency})`;
    updateComplianceInfo(sourceCurrency, destinationCurrency);

    if (!sourceCurrency || !destinationCurrency || !amount) {
        document.getElementById("res-fees").textContent = "—";
        document.getElementById("res-rate").textContent = "—";
        document.getElementById("res-receive").textContent = "—";
        return;
    }

    try {
        const query = new URLSearchParams({
            source: sourceCurrency,
            destination: destinationCurrency,
            amount,
        });
        const quote = await apiRequest(`/api/transfers/quote/?${query}`);
        if (requestId !== quoteRequest) return;

        document.getElementById("res-fees").textContent =
            formatCurrency(quote.fee, sourceCurrency);
        document.getElementById("res-rate").textContent =
            `1 ${sourceCurrency} = ${Number(quote.exchange_rate).toLocaleString("fr-FR", {
                maximumFractionDigits: 6,
            })} ${destinationCurrency}`;
        document.getElementById("res-receive").textContent =
            formatCurrency(quote.receive_amount, destinationCurrency);
    } catch (error) {
        if (requestId !== quoteRequest) return;
        document.getElementById("res-fees").textContent = "Indisponible";
        document.getElementById("res-rate").textContent = "—";
        document.getElementById("res-receive").textContent = "—";
        console.error("Quote request failed:", error);
    }
}

function openModal(type) {
    const modal = document.getElementById(`${type}-modal`);
    if (!modal) return;

    if (type === "transfer") {
        const form = modal.querySelector("form");
        const source = document.getElementById("source-country").value;
        const destination = document.getElementById("dest-country").value;
        const amount = document.getElementById("amount").value;
        form.elements.source_currency.value = source;
        form.elements.destination_currency.value = destination;
        form.elements.amount.value = amount;
        form.elements.idempotency_key.value = crypto.randomUUID();
        document.getElementById("transfer-summary").textContent =
            `Envoi de ${amount || "0"} ${source} vers ${destination}. Le prestataire confirmera le montant reçu.`;
        showFeedback("transfer-feedback", "");
    }
    if (type === "review") {
        showFeedback("review-feedback", "");
        loadEligibleTransfers();
    }

    activeModal = type;
    modal.classList.add("active");
    document.body.classList.add("modal-open");
    modal.querySelector("input, button:not(.modal-close)")?.focus();
}

function closeModal(type) {
    const modal = document.getElementById(`${type}-modal`);
    if (!modal) return;
    modal.classList.remove("active");
    document.body.classList.remove("modal-open");
    activeModal = null;
}

function switchModal(type) {
    document.querySelectorAll(".modal.active").forEach(modal => {
        modal.classList.remove("active");
    });
    document.body.classList.remove("modal-open");
    activeModal = null;
    openModal(type);
}

async function submitAuthForm(event, mode) {
    event.preventDefault();
    const form = event.currentTarget;
    const feedbackId = `${mode}-feedback`;
    showFeedback(feedbackId, "");
    const payload = {
        phone: form.elements.phone.value.trim(),
        password: form.elements.password.value,
    };
    if (mode === "register") payload.email = form.elements.email.value.trim();

    try {
        const result = await apiRequest(`/api/auth/${mode === "login" ? "login" : "register"}/`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        updateAccountUI(result.user);
        csrfToken = "";
        await ensureCsrfToken();
        form.reset();
        closeModal(mode);
        showFeedback("transfer-feedback", "");
    } catch (error) {
        showFeedback(feedbackId, error.message);
    }
}

async function submitTransferForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    showFeedback("transfer-feedback", "");
    const payload = {
        source_currency: form.elements.source_currency.value,
        destination_currency: form.elements.destination_currency.value,
        amount: form.elements.amount.value,
        idempotency_key: form.elements.idempotency_key.value,
        recipient_name: form.elements.recipient_name.value.trim(),
        recipient_phone: form.elements.recipient_phone.value.trim(),
    };

    try {
        const result = await apiRequest("/api/transfers/", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        showFeedback(
            "transfer-feedback",
            `Transfert enregistré. Statut : ${result.transfer.status}.`,
            false,
        );
    } catch (error) {
        if (error.status === 401) {
            closeModal("transfer");
            openModal("login");
            showFeedback("login-feedback", "Connectez-vous avant de confirmer l'envoi.");
            return;
        }
        showFeedback("transfer-feedback", error.message);
    }
}

function renderReviews(reviews) {
    const container = document.getElementById("approved-reviews");
    const emptyState = document.getElementById("reviews-empty");
    container.replaceChildren();
    emptyState.classList.toggle("hidden", reviews.length > 0);

    for (const review of reviews) {
        const article = document.createElement("article");
        article.className = "testimonial";
        const author = document.createElement("div");
        author.className = "testimonial-author";
        author.textContent = review.author;
        const text = document.createElement("p");
        text.className = "testimonial-text";
        text.textContent = review.text;
        const rating = document.createElement("div");
        rating.className = "testimonial-rating";
        rating.textContent = `Note vérifiée : ${review.rating}/5`;
        article.append(author, text, rating);
        container.append(article);
    }
}

async function loadReviews() {
    try {
        const data = await apiRequest("/api/reviews/");
        renderReviews(data.reviews);
    } catch (error) {
        document.getElementById("reviews-empty").textContent =
            "Les avis clients sont momentanément indisponibles.";
        console.error("Review request failed:", error);
    }
}

function updateAccountUI(user) {
    const loginButton = document.querySelector('[data-open-modal="login"]');
    const accountStatus = document.getElementById("account-status");
    const logoutButton = document.getElementById("logout-button");
    if (!user) {
        loginButton.classList.remove("hidden");
        accountStatus.classList.add("hidden");
        logoutButton.classList.add("hidden");
        accountStatus.textContent = "";
        return;
    }

    loginButton.classList.add("hidden");
    accountStatus.textContent = user.phone;
    accountStatus.classList.remove("hidden");
    logoutButton.classList.remove("hidden");
}

async function loadCurrentUser() {
    try {
        const data = await apiRequest("/api/auth/me/");
        updateAccountUI(data.user);
    } catch (error) {
        if (error.status !== 401) console.error("Session request failed:", error);
    }
}

async function loadEligibleTransfers() {
    const select = document.getElementById("review-transfer");
    const submitButton = document.getElementById("review-submit-button");
    select.disabled = false;
    submitButton.disabled = true;
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Chargement des transferts…";
    select.append(placeholder);

    try {
        const data = await apiRequest("/api/transfers/history/");
        const eligible = data.transfers.filter(transfer => transfer.can_review);
        select.replaceChildren();
        if (!eligible.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Aucun transfert terminé à évaluer";
            select.append(option);
            select.disabled = true;
            return;
        }
        select.disabled = false;
        submitButton.disabled = false;
        for (const transfer of eligible) {
            const option = document.createElement("option");
            option.value = transfer.id;
            option.textContent = `${formatCurrency(transfer.source_amount, transfer.source_currency)} vers ${transfer.recipient_name}`;
            select.append(option);
        }
    } catch (error) {
        if (error.status === 401) {
            closeModal("review");
            openModal("login");
            showFeedback("login-feedback", "Connectez-vous pour consulter vos transferts terminés.");
            return;
        }
        showFeedback("review-feedback", error.message);
    }
}

async function submitReviewForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    showFeedback("review-feedback", "");

    try {
        await apiRequest("/api/reviews/", {
            method: "POST",
            body: JSON.stringify({
                transfer_id: form.elements.transfer_id.value,
                rating: Number(form.elements.rating.value),
                text: form.elements.text.value.trim(),
            }),
        });
        form.reset();
        showFeedback(
            "review-feedback",
            "Merci. Votre avis est en attente de modération avant publication.",
            false,
        );
        await loadReviews();
    } catch (error) {
        if (error.status === 401) {
            closeModal("review");
            openModal("login");
            showFeedback("login-feedback", "Connectez-vous avant de soumettre un avis.");
            return;
        }
        showFeedback("review-feedback", error.message);
    }
}

document.addEventListener("click", event => {
    if (!(event.target instanceof Element)) return;

    const openButton = event.target.closest("[data-open-modal]");
    if (openButton) {
        openModal(openButton.dataset.openModal);
        return;
    }

    const closeButton = event.target.closest("[data-close-modal]");
    if (closeButton) {
        const modal = closeButton.closest(".modal");
        if (modal) closeModal(modal.id.replace(/-modal$/, ""));
        return;
    }

    const switchButton = event.target.closest("[data-switch-modal]");
    if (switchButton) {
        event.preventDefault();
        switchModal(switchButton.dataset.switchModal);
        return;
    }

    const logoutButton = event.target.closest('[data-action="logout"]');
    if (logoutButton) {
        apiRequest("/api/auth/logout/", { method: "POST" })
            .then(() => updateAccountUI(null))
            .catch(error => console.error("Logout failed:", error));
        return;
    }

    if (event.target.classList.contains("modal")) {
        closeModal(event.target.id.replace(/-modal$/, ""));
    }
});

document.addEventListener("submit", event => {
    if (!(event.target instanceof HTMLFormElement)) return;
    if (event.target.dataset.form === "login") submitAuthForm(event, "login");
    if (event.target.dataset.form === "register") submitAuthForm(event, "register");
    if (event.target.dataset.form === "transfer") submitTransferForm(event);
    if (event.target.dataset.form === "review") submitReviewForm(event);
});

document.addEventListener("keydown", event => {
    if (event.key === "Escape" && activeModal) closeModal(activeModal);
});

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("source-country").addEventListener("change", updateDestinationOptions);
    document.getElementById("dest-country").addEventListener("change", calculate);
    document.getElementById("amount").addEventListener("input", calculate);
    initializeCurrencySelectors().catch(error => {
        console.error("Currency API failed:", error);
        document.getElementById("res-fees").textContent = "Indisponible";
        document.getElementById("res-rate").textContent = "—";
        document.getElementById("res-receive").textContent = "—";
    });
    loadReviews();
    loadCurrentUser();
});
