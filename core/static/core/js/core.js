
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
            adaptRecuadroFondo()
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

    const html = document.querySelector('html');
    html.setAttribute('data-bs-theme', themeValue);

    // Llamar a la función que edita el menú de cambio de tema según corresponda
    editThemeToggleMenu(themeValue);

    // Llamar a la función que cambia la imagen de fondo
    setBackgroundImageAndButtons(themeValue);

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
    var themeLightCheckbox = document.getElementById("theme-light");
    var themeDarkCheckbox = document.getElementById("theme-dark");
    
    // Obtener el elemento del botón y los íconos
    var themeButton = document.getElementById("theme-button");
    if (themeButton) {
        // Mostrar u ocultar las marcas de verificación correspondientes
        if (themeValue === "light") {
            themeLightCheckbox.style.display = "block";
            themeDarkCheckbox.style.display = "none";
        } else if (themeValue === "dark") {
            themeLightCheckbox.style.display = "none";
            themeDarkCheckbox.style.display = "block";
        }
        // Cambiar la clase del botón para cambiar tema según el tema seleccionado
        themeButton.classList.remove("bi-sun-fill", "bi-moon-stars-fill", "bi-circle-half-fill");
        themeButton.classList.add(getIconClass(themeValue));
        
        // Actualizar el color de los SVG según el tema seleccionado
        setSvgsImages(themeValue);
    }
}

function getIconClass(themeValue) {
    if (themeValue === "light") {
        return "bi-sun-fill";
    } else if (themeValue === "dark") {
        return "bi-moon-stars-fill";
    } 
}

function setSvgsImages(themeValue) {
    const svgSun = document.querySelectorAll('.bi-sun-fill');
    svgSun.forEach(svg => {
      if (themeValue === "light") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23332F2E' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708' clip-rule='evenodd'/></svg>")`;
      } else if (themeValue === "dark") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23C2C4C8' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0m0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13m8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5M3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8m10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0m-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0m9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707M4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708' clip-rule='evenodd'/></svg>")`;
      }
    });
    const svgMoon = document.querySelectorAll('.bi-moon-stars-fill');
    svgMoon.forEach(svg => {
      if (themeValue === "light") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23332F2E' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278' clip-rule='evenodd'/><path fill-rule='evenodd' d='M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.73 1.73 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.73 1.73 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.73 1.73 0 0 0 1.097-1.097zM13.863.099a.145.145 0 0 1 .274 0l.258.774c.115.346.386.617.732.732l.774.258a.145.145 0 0 1 0 .274l-.774.258a1.16 1.16 0 0 0-.732.732l-.258.774a.145.145 0 0 1-.274 0l-.258-.774a1.16 1.16 0 0 0-.732-.732l-.774-.258a.145.145 0 0 1 0-.274l.774-.258c.346-.115.617-.386.732-.732z' clip-rule='evenodd'/></svg>")`;
      } else if (themeValue === "dark") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23C2C4C8' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M6 .278a.77.77 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277q.792-.001 1.533-.16a.79.79 0 0 1 .81.316.73.73 0 0 1-.031.893A8.35 8.35 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.75.75 0 0 1 6 .278' clip-rule='evenodd'/><path fill-rule='evenodd' d='M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.73 1.73 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.73 1.73 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.73 1.73 0 0 0 1.097-1.097zM13.863.099a.145.145 0 0 1 .274 0l.258.774c.115.346.386.617.732.732l.774.258a.145.145 0 0 1 0 .274l-.774.258a1.16 1.16 0 0 0-.732.732l-.258.774a.145.145 0 0 1-.274 0l-.258-.774a1.16 1.16 0 0 0-.732-.732l-.774-.258a.145.145 0 0 1 0-.274l.774-.258c.346-.115.617-.386.732-.732z' clip-rule='evenodd'/></svg>")`;
      }
    });
    const svgCheck = document.querySelectorAll('.bi-check2');
    svgCheck.forEach(svg => {
      if (themeValue === "light") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23332F2E' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0' clip-rule='evenodd'/></svg>")`;
      } else if (themeValue === "dark") {
        svg.style.backgroundImage = `url("data:image/svg+xml,<svg viewBox='0 0 16 16' fill='%23C2C4C8' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0' clip-rule='evenodd'/></svg>")`;
      }
    });
  }

// Función que modifica la clase de un div en el template base para cambiar la imagen de fondo.
function setBackgroundImageAndButtons(themeValue) {

    // Cambiar la clase de la imagen de fondo según el tema seleccionado
    const imagenFondo = document.querySelector('.imagen-fondo');
    imagenFondo.classList.remove('imagen-fondo-light', 'imagen-fondo-dark');
    imagenFondo.classList.add(`imagen-fondo-${themeValue}`);
    
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
function editLogin(themeValue) {
    const navBar = document.querySelector('.navbar');
    navBar.classList.remove('navbar-light', 'navbar-dark');
    navBar.classList.remove('bg-light', 'bg-dark');
    navBar.classList.add(`navbar-${themeValue}`);
    navBar.classList.add(`bg-${themeValue}`);
    const recuadroLogin = document.querySelector('.recuadro-fondo-login');
    const btn = document.getElementById('submit');
    // Verificar el valor del tema elegido
    if (themeValue === 'dark') {
        recuadroLogin.classList.remove('light');
        recuadroLogin.classList.add('dark'); 
        btn.classList.remove('btn-light');
        btn.classList.add('btn-dark');
    } else {
        recuadroLogin.classList.remove('dark');
        recuadroLogin.classList.add('light');
        btn.classList.remove('btn-dark');
        btn.classList.add('btn-light');
    }
}

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

function adaptRecuadroFondo() {
    const contenidoPrincipal = document.querySelector('.ContenidoPrincipal');

    // Ajusta el ancho del recuadro al 90% del viewport
    const viewportWidth = window.innerWidth;
    contenidoPrincipal.style.width = `${viewportWidth * 0.9}px`;

}

window.addEventListener('resize', () => adaptRecuadroFondo());
window.addEventListener('load', () => adaptRecuadroFondo());