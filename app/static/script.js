document.addEventListener("DOMContentLoaded", function() {
    
    // Pega todos os botões de logoff (tanto o do mobile quanto o do desktop)
    const btnLogoffElements = document.querySelectorAll(".btn-logoff");

    btnLogoffElements.forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault(); // Evita que a página recarregue imediatamente
            
            // Aqui você pode colocar a lógica real de desconectar (chamar rota do Flask, limpar cookies, etc)
            const confirmar = confirm("Tem certeza que deseja sair do sistema?");
            
            if (confirmar) {
                // Simula o logoff redirecionando para uma página de login
                alert("Logoff realizado com sucesso!");
                window.location.href = "/"; // Pode mudar para /login depois
            }
        });
    });

});