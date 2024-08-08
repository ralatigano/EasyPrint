// window.addEventListener("load", async() => {
//     document.getElementById("nav_item_usuarios").style.fontWeight = "bold";
// });
document.addEventListener('DOMContentLoaded', function() {
    function ajustarFondo() {
        // Seleccionar los elementos
        const contenidoPrincipal = document.querySelector('.ContenidoPrincipal');
        const contenedor = document.querySelector('.container.mt-5');
        const fondo = document.querySelector('.recuadro-fondo-register');

        if (contenedor && fondo) {
            // Obtener las dimensiones del contenedor
            const anchoContenedor = contenedor.offsetWidth;
            const altoContenedor = contenedor.offsetHeight;

            // Ajustar las dimensiones del fondo
            fondo.style.width = `${anchoContenedor * 1.15}px`;
            fondo.style.height = `${altoContenedor * 1.15}px`;

            // Ajustar el tamaño del contenido principal
            contenidoPrincipal.style.minHeight = altoContenedor * 1.1 + 'px';

            // Ajustar la posición del fondo para que esté centrado detrás del contenido
            //fondo.style.position = 'absolute';
            //fondo.style.top = `${contenedor.offsetTop - (altoContenedor * 0.075)}px`; // Ajuste para centrar verticalmente
            //fondo.style.left = `${contenedor.offsetLeft - (anchoContenedor * 0.075)}px`; // Ajuste para centrar horizontalmente
        }
    }

    // Ajustar el fondo cuando la página se carga y cuando se redimensiona
    ajustarFondo();
    window.addEventListener('resize', ajustarFondo);
});