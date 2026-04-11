let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Usuarios.
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Usuarios").DataTable({
        language: {
            lengthMenu: 'Mostrar _MENU_ productos por página',
            zeroRecords: 'No hay productos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ productos',
            infoEmpty: 'No hay productos',
            InfoFiltered: '(filtrado de _MAX_ productos totales)',
            search: 'Buscar:',
            LoadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Ultimo',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        }
    });
    dataTableIsInitilized=true;
}

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_usuarios").style.fontWeight = "bold";
});

//Lógica que ajusta las dimensiones de algunos elementos cuando se redimensiona la página.
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

        }
    }

    // Ajustar el fondo cuando la página se carga y cuando se redimensiona
    ajustarFondo();
    window.addEventListener('resize', ajustarFondo);
});

document.addEventListener('DOMContentLoaded', () => {
    console.log('Usuarios.js cargado');
    const modalUsuarioEl = document.getElementById('modalUsuario');

    if (!modalUsuarioEl) return;

    const modalUsuario = new bootstrap.Modal(modalUsuarioEl);

    // Referencias a campos del formulario
    const userIdInput        = document.getElementById('user_id');
    const cambiarPasswordInput = document.getElementById('cambiar_password');
    const firstNameInput     = document.getElementById('first_name');
    const lastNameInput      = document.getElementById('last_name');
    const emailInput         = document.getElementById('email');
    const telefonoInput      = document.getElementById('telefono');
    const grupoSelect        = document.getElementById('grupo');
    const usernameInput      = document.getElementById('username');
    const passwordInput      = document.getElementById('password');
    const password2Input     = document.getElementById('password2');
    const modalTitulo        = document.getElementById('modalUsuarioTitulo');

    const passwordBlock      = document.getElementById('password-block');
    const passwordToggleBlock = document.getElementById('password-toggle-block');
    const toggleCambiarPassword = document.getElementById('toggleCambiarPassword');
    const passwordError      = document.getElementById('password-error');

    const usernameError      = document.getElementById('username-error');
    const usernameSuggestionsBox = document.getElementById('username-suggestions');
    const usernameSuggestionList = document.getElementById('username-suggestion-list');

    let usernameFueAutogenerado = true;
    let usernameUltimaSugerencia = '';

    // ── Limpiar formulario ────────────────────────────────────────────────────
    function limpiarFormulario() {
        userIdInput.value = '0';
        cambiarPasswordInput.value = '0';
        firstNameInput.value = '';
        lastNameInput.value = '';
        emailInput.value = '';
        telefonoInput.value = '';
        grupoSelect.value = '';
        usernameInput.value = '';
        passwordInput.value = '';
        password2Input.value = '';

        usernameInput.classList.remove('is-invalid');
        passwordInput.classList.remove('is-invalid');
        password2Input.classList.remove('is-invalid');
        usernameError.classList.add('d-none');
        usernameSuggestionsBox.classList.add('d-none');
        usernameSuggestionList.innerHTML = '';
        passwordError.classList.add('d-none');

        toggleCambiarPassword.checked = false;
        usernameFueAutogenerado = true;
        usernameUltimaSugerencia = '';
    }

    // ── Autogenerar username desde nombre + apellido ──────────────────────────
    function autogenerarUsername() {
        const nombre = (firstNameInput.value || '').trim();
        const apellido = (lastNameInput.value || '').trim();
        if (!nombre || !apellido) return;
        if (!usernameFueAutogenerado && usernameInput.value && usernameInput.value !== usernameUltimaSugerencia) return;

        const inicial = nombre.split(' ').filter(p => p)[0][0].toLowerCase();
        const base = apellido.toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/\s+/g, '');
        const sugerido = `${inicial}${base}`;

        usernameInput.value = sugerido;
        usernameUltimaSugerencia = sugerido;
        usernameFueAutogenerado = true;
        validarUsernameDebounced();
    }

    // ── Validación username en tiempo real ────────────────────────────────────
    function marcarUsernameInvalido(exists, suggestions) {
        if (exists) {
            usernameInput.classList.add('is-invalid');
            usernameError.classList.remove('d-none');
            if (suggestions && suggestions.length > 0) {
                usernameSuggestionsBox.classList.remove('d-none');
                usernameSuggestionList.innerHTML = '';
                suggestions.forEach(s => {
                    const span = document.createElement('span');
                    span.textContent = s;
                    span.classList.add('badge', 'bg-secondary', 'me-1', 'username-suggestion');
                    span.style.cursor = 'pointer';
                    usernameSuggestionList.appendChild(span);
                });
            } else {
                usernameSuggestionsBox.classList.add('d-none');
            }
        } else {
            usernameInput.classList.remove('is-invalid');
            usernameError.classList.add('d-none');
            usernameSuggestionsBox.classList.add('d-none');
            usernameSuggestionList.innerHTML = '';
        }
    }

    function validarUsername() {
        const username = (usernameInput.value || '').trim();
        if (!username) { marcarUsernameInvalido(false, []); return; }

        const userId = userIdInput.value || '0';
        const params = new URLSearchParams({ u: username, user_id: userId });

        fetch(`/usuarios/validar-username?${params}`)
            .then(res => res.json())
            .then(data => marcarUsernameInvalido(data.exists, data.suggestions || []))
            .catch(() => {});
    }

    let usernameTimeout = null;
    function validarUsernameDebounced() {
        clearTimeout(usernameTimeout);
        usernameTimeout = setTimeout(validarUsername, 300);
    }

    // ── Validación contraseñas en tiempo real ─────────────────────────────────
    function validarPasswords() {
        const p1 = passwordInput.value;
        const p2 = password2Input.value;
        if (!p1 && !p2) {
            passwordError.classList.add('d-none');
            passwordInput.classList.remove('is-invalid');
            password2Input.classList.remove('is-invalid');
            return;
        }
        if (p1 !== p2) {
            passwordError.classList.remove('d-none');
            passwordInput.classList.add('is-invalid');
            password2Input.classList.add('is-invalid');
        } else {
            passwordError.classList.add('d-none');
            passwordInput.classList.remove('is-invalid');
            password2Input.classList.remove('is-invalid');
        }
    }

    // ── Abrir modal para CREAR ────────────────────────────────────────────────
    function abrirModalNuevo() {
        limpiarFormulario();
        modalTitulo.textContent = 'Agregar usuario';
        passwordBlock.classList.remove('d-none');
        passwordToggleBlock.classList.add('d-none');
        modalUsuario.show();
    }

    document.getElementById('btn-agregar-usuario')?.addEventListener('click', abrirModalNuevo);

    // ── Abrir modal para EDITAR ───────────────────────────────────────────────
    document.querySelectorAll('.btn-editar-usuario').forEach(btn => {
        btn.addEventListener('click', () => {
            const userId = btn.dataset.id;
            limpiarFormulario();
            modalTitulo.textContent = 'Editar usuario';

            fetch(`/usuarios/info/${userId}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) return;
                    userIdInput.value        = data.id;
                    firstNameInput.value     = data.first_name;
                    lastNameInput.value      = data.last_name;
                    emailInput.value         = data.email;
                    telefonoInput.value      = data.telefono;
                    usernameInput.value      = data.username;
                    usernameUltimaSugerencia = data.username;
                    usernameFueAutogenerado  = false;

                    if (data.grupos && data.grupos.length > 0) {
                        grupoSelect.value = data.grupos[0];
                    }

                    // En edición: ocultar campos de contraseña, mostrar toggle
                    passwordBlock.classList.add('d-none');
                    passwordToggleBlock.classList.remove('d-none');
                    cambiarPasswordInput.value = '0';

                    modalUsuario.show();
                });
        });
    });

    // ── Toggle cambiar contraseña (en edición) ────────────────────────────────
    toggleCambiarPassword.addEventListener('change', () => {
        if (toggleCambiarPassword.checked) {
            passwordBlock.classList.remove('d-none');
            cambiarPasswordInput.value = '1';
        } else {
            passwordBlock.classList.add('d-none');
            cambiarPasswordInput.value = '0';
            passwordInput.value = '';
            password2Input.value = '';
            passwordError.classList.add('d-none');
            passwordInput.classList.remove('is-invalid');
            password2Input.classList.remove('is-invalid');
        }
    });

    // ── Limpiar modal al cerrarlo ─────────────────────────────────────────────
    modalUsuarioEl.addEventListener('hidden.bs.modal', limpiarFormulario);

    // ── Eventos de inputs ─────────────────────────────────────────────────────
    firstNameInput.addEventListener('input', autogenerarUsername);
    lastNameInput.addEventListener('input', autogenerarUsername);
    usernameInput.addEventListener('input', () => {
        usernameFueAutogenerado = false;
        validarUsernameDebounced();
    });
    usernameSuggestionList.addEventListener('click', e => {
        if (e.target.classList.contains('username-suggestion')) {
            usernameInput.value = e.target.textContent;
            usernameUltimaSugerencia = e.target.textContent;
            usernameFueAutogenerado = true;
            validarUsernameDebounced();
        }
    });
    passwordInput.addEventListener('input', validarPasswords);
    password2Input.addEventListener('input', validarPasswords);


});