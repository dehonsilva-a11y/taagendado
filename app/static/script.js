/* Lello Imóveis · comportamentos globais do front */
document.addEventListener("DOMContentLoaded", function () {

    // 1) Toasts (mensagens flutuantes): o Bootstrap só mostra se for inicializado
    document.querySelectorAll(".toast").forEach(function (el) {
        new bootstrap.Toast(el, { delay: 5000, autohide: true }).show();
    });

    // 2) Alertas temporários somem sozinhos depois de 10 segundos
    setTimeout(function () {
        document.querySelectorAll(".alert-temporario").forEach(function (el) {
            bootstrap.Alert.getOrCreateInstance(el).close();
        });
    }, 10000);

    // 3) Data de hoje por extenso: <span data-today></span>
    document.querySelectorAll("[data-today]").forEach(function (el) {
        const txt = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
        el.textContent = txt.charAt(0).toUpperCase() + txt.slice(1);
    });

    // 4) Confirmações: <button data-confirm="Mensagem">
    document.querySelectorAll("[data-confirm]").forEach(function (el) {
        el.addEventListener("click", function (e) {
            if (!confirm(el.getAttribute("data-confirm"))) e.preventDefault();
        });
    });

    // 5) Evita clique duplo em formulários (desativa o botão de envio após enviar)
    document.querySelectorAll("form[data-once]").forEach(function (form) {
        form.addEventListener("submit", function () {
            form.querySelectorAll("[type=submit]").forEach(function (b) { b.disabled = true; });
        });
    });
});
