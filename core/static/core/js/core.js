
// Este bloque de código se ejecuta al cargar la página y lo que hace es verificar si hay una preferencia de tema almacenada en el navegador
// y si es así establece el tema en función de eso. Caso contrario verifica la preferencia del usuario y establece el tema correspondiente.
// Finalmente se agrega un evento de escucha para detectar cambios en la preferencia de tema del usuario.
document.addEventListener("DOMContentLoaded", function() {
    // Verificar si hay una preferencia de tema almacenada en el almacenamiento local
    const storedTheme = localStorage.getItem('theme');
    // Si no hay una preferencia de tema almacenada, verificar la preferencia del usuario en el servidor
    $.ajax({
        url: '/getDarkMode',
        method: 'GET',
        dataType: 'json',
        success: function(data) {
            const darkMode = data.dark_mode;
            setTheme(darkMode);
            // Llamar función que adapta el recuadro de fondo
            // adaptRecuadroFondo()
        },
        error: function() {
            // Establecer el tema en función de las preferencias obtenidas
            if (storedTheme) {
                setTheme(storedTheme);
            } else {
            // Si hay un error al obtener la preferencia del usuario en el servidor, utilizar la preferencia según la API
                const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)').matches;
                setTheme(prefersDarkScheme ? 'dark' : 'light');    
            }
        }
    });
    // Agregar un evento de escucha para detectar cambios en la preferencia de tema del usuario
    const mediaQueryList = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQueryList.addEventListener('change', function(event) {
        setTheme(event.matches ? 'dark' : 'light');
    });

});

// Esta es la función que hace toda la magia. Incluida la llamada a otras funciones que cambian partes de la estructura del tema.
function setTheme(themeValue) {

    const html = document.querySelector('body');
    html.setAttribute('data-bs-theme', themeValue);
    const recuadroSemifondo = document.querySelector('.recuadro-semifondo');

    // Llamar a la función que edita el menú de cambio de tema según corresponda
    editThemeToggleMenu(themeValue);

    // Llamar a la función que cambia la imagen de fondo
    setBackgroundImageAndButtons(themeValue);

    if (recuadroSemifondo) {
        recuadroSemifondo.classList.remove('light', 'dark');
        recuadroSemifondo.classList.add(themeValue);
    }

    // Comprobar la existencia del navbar antes de llamar a editNavBar
    const recuadroFondoLogin = document.querySelector('.recuadro-fondo-login'); 
    if (!recuadroFondoLogin) {
        editNavBar(themeValue);
    }else {
        editLogin(themeValue);
    }
    const recuadroFondoRegister = document.querySelector('.recuadro-fondo-register'); 
    if (recuadroFondoRegister) {
        editRegister(themeValue);
    }

    editSomeElements(themeValue);

    // Almacenar la preferencia de tema en el almacenamiento local
    localStorage.setItem('theme', themeValue);
}

// Función para cambiar el tema al clickear en un botón obteniendo el valor de la clase data-bs-theme-value y llamando a la función setTheme
function handleThemeChange(event) { 
    const themeValue = event.target.dataset.bsThemeValue; 
    setTheme(themeValue);

}

// Agregar evento de clic a los botones de tema, cuando ocurra un click en los botones, se llamara a la función handleThemeChange.
const themeButtons = document.querySelectorAll('[data-bs-theme-value]'); 
themeButtons.forEach(button => { 
    button.addEventListener('click', handleThemeChange); 
});

// Función que modifica algunos atributos del menú desplegable de cambio de tema de modo que quede claro cual es el tema actual y los elementos
// contrasten apropiadamente con el tema elegido.
function editThemeToggleMenu(themeValue) {
    // Obtener los elementos de las marcas de verificación
    var themeLightCheckbox = document.getElementById("check-light");
    var themeDarkCheckbox = document.getElementById("check-dark");
    var themeLightCheckboxDesktop = document.getElementById("check-light-desktop");
    var themeDarkCheckboxDesktop = document.getElementById("check-dark-desktop");

    // Mostrar u ocultar las marcas de verificación correspondientes
    if (themeValue === "light") {
        themeLightCheckbox?.classList.remove("d-none");
        themeDarkCheckbox?.classList.add("d-none");
        themeLightCheckboxDesktop?.classList.remove("d-none");
        themeDarkCheckboxDesktop?.classList.add("d-none");
    } else if (themeValue === "dark") {
        themeLightCheckbox?.classList.add("d-none");
        themeDarkCheckbox?.classList.remove("d-none");
        themeLightCheckboxDesktop?.classList.add("d-none");
        themeDarkCheckboxDesktop?.classList.remove("d-none");
    }

}

// Función que modifica el ícono del botón de tema
function getIconClass(themeValue) {
    if (themeValue === "light") {
        return "bi-sun-fill";
    } else if (themeValue === "dark") {
        return "bi-moon-stars-fill";
    } 
}


// Función que modifica la clase de un div en el template base para cambiar la imagen de fondo.
function setBackgroundImageAndButtons(themeValue) {

    // Cambiar la clase de la imagen de fondo según el tema seleccionado

    const body = document.body;
    body.classList.remove('theme-light', 'theme-dark');
    body.classList.add(`theme-${themeValue}`);
    const btnElements = document.querySelectorAll('.btn');
    // Verificar si hay botones en el template
    if (btnElements.length > 0) {
        // Iterar sobre los botones seleccionados
        btnElements.forEach(btn => {
            // Verificar el valor del tema seleccionado
            if (themeValue === 'dark') {
                // Aplicar estilos para el tema oscuro
                btn.classList.remove('btn-outline-dark', 'btn-light');
                btn.classList.add('btn-outline-light', 'btn-dark');
            } else {
                // Aplicar estilos para el tema claro
                btn.classList.remove('btn-outline-light', 'btn-dark');
                btn.classList.add('btn-outline-dark', 'btn-light');
            }
        });
    }

    const iconoEnlaceDirecto = document.getElementById('iconoBrand');
    const iconos = {
        light: '/static/core/img/light/easy_light.ico',
        dark: '/static/core/img/dark/easy_dark.ico',
      };
    
      iconoEnlaceDirecto.href = iconos[themeValue];


    // Cambiar el color del texto de la versión según el tema seleccionado
    const tesxtoVersion = document.querySelector('.version');
    if (themeValue === "light") {
        tesxtoVersion.style.color = `#332F2E`;
    } else if (themeValue === "dark") {
        tesxtoVersion.style.color = `#C2C4C8`;
    }
}

// Función que modifica algunos atributos de algunos elementos del navBar de modo de lograr un contraste apropiado.
function editNavBar(themeValue) {
    // Cambia el texto y la imagen del navBar
    const navBar = document.querySelector('.navbar');
    navBar.classList.remove('navbar-light', 'navbar-dark');
    navBar.classList.remove('bg-light', 'bg-dark');
    navBar.classList.add(`navbar-${themeValue}`);
    navBar.classList.add(`bg-${themeValue}`);

    // Obtener la referencia al elemento img
    const imgElement = document.getElementById('brand');
    // Verificar el valor del tema elegido
    if (themeValue === 'dark') {
        // Cambiar el atributo src a la imagen correspondiente al tema oscuro
        imgElement.setAttribute('src', '/static/core/img/dark/Isologotipo_easy_dark.png'); 
    } else {
        // Cambiar el atributo src a la imagen correspondiente al tema claro
        imgElement.setAttribute('src', '/static/core/img/light/Isologotipo_easy_light.png');
    }
}

// Función que modifica algunos elementos de la vista de inicio de sesión
function editLogin(themeValue) {

    const btn = document.getElementById('submit');
    const logo = document.getElementById('logo_login');
    // Verificar el valor del tema elegido
    if (themeValue === 'dark') {
        logo.classList.remove('light_login');
        logo.classList.add('dark_login');
        btn.classList.remove('btn-light');
        btn.classList.add('btn-dark');
    } else {
        logo.classList.remove('dark_login');
        logo.classList.add('light_login');
        btn.classList.remove('btn-dark');
        btn.classList.add('btn-light');
    }
}

// Función que modifica algunas clases mas generales de varios elementos en función del tema elegido.
// Un pequeño intento por manejar el cambio de tema de forma mas global.
function editSomeElements(themeValue) {
    var elements = document.querySelectorAll('.light_bg, .dark_bg');
        
    elements.forEach(function(element) {
        if (themeValue === 'dark') {
            element.classList.remove('light_bg');
            element.classList.add('dark_bg');
            element.style.backgroundColor = '#474973';
        } else if (themeValue === 'light') {
            element.classList.remove('dark_bg');
            element.classList.add('light_bg');
            element.style.backgroundColor = '#B1DE43';
        }
    });
}

// Función que modifica elementos de la vista de registro. 
function editRegister(themeValue) {
    const recuadroRegister = document.querySelector('.recuadro-fondo-register');
    const btn = document.querySelector('.btn');
    // Verificar el valor del tema elegido
    if (themeValue === 'dark') {
        recuadroRegister.classList.remove('light');
        recuadroRegister.classList.add('dark'); 
        btn.classList.remove('btn-outline-light', 'btn-primary');
        btn.classList.add('btn-dark');
    } else {
        recuadroRegister.classList.remove('dark');
        recuadroRegister.classList.add('light');
        btn.classList.remove('btn-outline-dark', 'btn-primary');
        btn.classList.add('btn-light');
    }   
}

// Función que modifica la distribución de elementos del navBar para adaptarse a pantallas pequeñas.
document.addEventListener('DOMContentLoaded', function() {
    const profileImgToggler = document.getElementById('profile-img-toggler');
    const navbarTogglerIcon = document.querySelector('.navbar-toggler-icon');
    const navbarToggler = document.getElementById('navbar-toggler');
    const imgPerfilNormal = document.getElementById('profile-img');

    function toggleNavbar() {
        const isMobile = window.innerWidth < 992;

        if (isMobile) {
            if (profileImgToggler) {
                profileImgToggler.classList.remove('d-none');
                profileImgToggler.classList.add('d-inline');
            }
            if (navbarTogglerIcon) {
                navbarTogglerIcon.classList.add('d-none');
            }
            if (imgPerfilNormal) {
                imgPerfilNormal.classList.add('d-none');
            }
        } else {
            if (profileImgToggler) {
                profileImgToggler.classList.add('d-none');
                profileImgToggler.classList.remove('d-inline');
            }
            if (navbarTogglerIcon) {
                navbarTogglerIcon.classList.remove('d-none');
            }
            if (imgPerfilNormal) {
                imgPerfilNormal.classList.remove('d-none');
            }
        }
    }

    // Evento para detectar el cambio de tamaño de la pantalla
    window.addEventListener('resize', toggleNavbar);

    if (navbarToggler) {
        // Evento para el click del toggler
        navbarToggler.addEventListener('click', toggleNavbar);
    }

    // Comprobación inicial
    toggleNavbar();
});

const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))


// Convierte un número real a formato es-AR (coma + miles + 2 decimales)
function formatearNumeroLocal(valor) {
    if (valor === null || valor === undefined || valor === "") return "";
    const numero = Number(valor);
    if (isNaN(numero)) return "";
    return numero.toLocaleString("es-AR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Convierte un string formateado (1.234,56) a número real JS (1234.56)
function parsearNumeroLocal(str) {
    if (!str) return 0;

    // Elimina separadores de miles
    let limpio = str.replace(/\./g, "");

    // Reemplaza coma decimal por punto
    limpio = limpio.replace(",", ".");

    const numero = Number(limpio);
    return isNaN(numero) ? 0 : numero;
}

// ── Show/hide contraseña ──────────────────────────────────────────────────
document.addEventListener('click', e => {
    const btn = e.target.closest('.toggle-password');
    if (!btn) return;
    const input = document.getElementById(btn.getAttribute('data-target'));
    if (!input) return;
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
});