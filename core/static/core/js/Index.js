
// Inicializar DataTable y otros elementos después de que el DOM esté completamente cargado
document.addEventListener("DOMContentLoaded", async() => {
    await initDataTable();
    document.getElementById("nav_item_inicio").style.fontWeight = "bold";
});

let dataTable;
let dataTableIsInitilized=false;
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#NuevoPresupuesto").DataTable({
        responsive: true,
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
    dataTable.on('draw.dt', function() {
        footerCallback(null, dataTable.data(), 0, dataTable.data().length, {});
    });


};

/* Funcionalidad para evitar la eliminación de objetos listados en la cotización por un click involuntario. */
(function () {
    const btnEliminacion = document.querySelectorAll(".btnEliminacion");
    btnEliminacion.forEach(btn=>{
        btn.addEventListener("click", (e)=>{
            const confirmacion = confirm("¿Está segur@ de que desea eliminar este elemento?");
            if(!confirmacion){
                e.preventDefault();
            }    
        });
    });
})();

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
        }
    }
    }
    return cookieValue;
}

// Función que abre el modal con los datos del cálculo realizado. En este modal se puede decidir si incorporar el producto al presupuesto actual o no.
function previoModal() {
    const form = document.getElementById('nueva_cotizacion_form');
    const formData = new FormData(form);

    // Mostrar el modal antes de realizar la llamada fetch
    var modal = new bootstrap.Modal(document.getElementById('resultadoPrevioModal'), {
        keyboard: false
    });
    modal.show();

    fetch('/presupuestos/calculoRapido', {
        method: 'POST',
        body: formData,
        headers: {
        'X-CSRFToken': getCookie('csrftoken')
        }
    })

    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            document.getElementById('prod_prev').innerText = data.producto;
            document.getElementById('cant_prev').innerText = data.cantidad_repeticion;
            document.getElementById('cant_area_prev').innerText = data.cant_area;
            document.getElementById('precio_prev').innerText = data.precio;
            document.getElementById('empaquetado_prev').innerText = data.empaquetado;
            document.getElementById('t_produccion_prev').innerText = data.t_produccion;
            document.getElementById('detalle_prev').innerText =  data.detalle;
            document.getElementById('descuento_prev').innerText = data.descuento === 0 ? '0 %' : data.descuento +'%';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Hubo un error al procesar la solicitud.');
    })
};


//Función que escucha el evento click sobre el botón de editar un producto y muestra un modal con los datos del producto que se pueden editar.
document.addEventListener('DOMContentLoaded', function() {
    var editarProductoPresupuestoModal = document.getElementById('editarProductoPresupuestoModal');
    editarProductoPresupuestoModal.addEventListener('show.bs.modal', function(event) {
        var button = event.relatedTarget;
        var data = button.getAttribute('data-bs-whatever').split(' | ');
        //{{c.codigo}} | {{c.nombre}} | {{c.info_adic}} | {{c.cantidad}} | {{c.cant_area}} | {{c.desc_porcentaje}} | {{c.empaquetado}} | {{c.t_produccion}} | {{c.precio}}
        var codigo = data[0];
        var nombre = data[1];
        var infoAdic = data[2];
        var cantidad = data[3];
        var cant_area = data[4];
        var descPorcentaje = data[5];
        var empaquetado = data[6] === 'True';
        var tProduccion = data[7];
        var precio = data[8];
        // Actualizar los campos del modal
        document.getElementById('cod_edit').value = codigo;
        document.getElementById('prod_edit').value = nombre;
        document.getElementById('detalle_edit').value = infoAdic;
        document.getElementById('cant_edit').value = cantidad;
        document.getElementById('cant_area_edit').value = cant_area;
        document.getElementById('desc_edit').value = descPorcentaje;
        document.getElementById('t_prod_edit').value = tProduccion;
        document.getElementById('precio_edit').value = precio;
        // Evaluar el dato que viene en empaquetado para saber si rellenar o no el checkbox
        var empaqEditCheckbox = document.getElementById('empaq_edit');
        if (empaquetado) {
            empaqEditCheckbox.checked = true;
        } else {
            empaqEditCheckbox.checked = false;
        }
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('#navbarSupportedContent');

    // Escucha eventos de Bootstrap para ajustar el estado del botón
    navbarCollapse.addEventListener('show.bs.collapse', function() {
      navbarToggler.setAttribute('aria-expanded', 'true');
    });

    navbarCollapse.addEventListener('hide.bs.collapse', function() {
      navbarToggler.setAttribute('aria-expanded', 'false');
    });
});

//----------------------------------------------------------Lógica nueva para la cotización
document.addEventListener("DOMContentLoaded", function () {
    var imgElement = document.getElementById('img_hoja');
    var btnDescargar = document.getElementById('btnDescargarGrafico');
    var btnBorrar = document.getElementById('btnBorrarGrafico');
    var graficoContenedor = document.getElementById('grafico_contenedor');
    var tituloGrafico = document.getElementById('tituloGrafico');
    var pResultado = document.getElementById('resultado');

    // Lógica para descargar el gráfico
    btnDescargar.onclick = function () {
        event.preventDefault();
        console.log('Descargar gráfico, URL:', imgElement.src);  // Añadido
        descargarGrafico(imgElement.src);
    };

    // Lógica para borrar el gráfico
    btnBorrar.onclick = function () {
        event.preventDefault();
        console.log('Borrar gráfico, URL:', imgElement.src);  // Añadido
        borrarGrafico();
    };
    //Función que responde al click del botón que permite la descarga del gráfico.
    function descargarGrafico(url) {
        var link = document.createElement('a');
        link.href = url;
        link.download = 'grafico.png';  // Puedes personalizar el nombre
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    //Función que responde al click sobre el botón de borrado del gráfico. Se aprovecha esta función para borrar todos los gráficos que se podrían haber generado durante la cotización.
    function borrarGrafico() {
        // Envía la solicitud al servidor para eliminar la imagen
        fetch('/presupuestos/borrarImagenGenerada', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),  // Asegúrate de tener tu token CSRF
                'Content-Type': 'application/json'
            },
        })
        .then(response => response.json())
        .then(data => {
            console.log('Imagen eliminada:', data.message);  // Añadido
            // Limpiar la imagen y ocultar los botones
            imgElement.src = '';
            graficoContenedor.classList.add('hidden');
        })
        .catch(error => {
            console.error('Error al eliminar la imagen:', error);
        });
    }

    function generarGrafico(algoritmo) {
        var categoria = $('#categoria').val();
        var cantidad_repeticion = $('#cantidad_repeticion').val();
        var ancho = $('#ancho').val();
        var alto = $('#alto').val();
        var separacion = $('#separacion').val();


        // Realiza una solicitud AJAX a una función del backend que hace los cálculos necesarios para realizar el gráfico y para continuar con la cotización.
        $.ajax({
            url: '/presupuestos/productosPorCategoria/',  // La URL de la vista Django
            type: 'POST',
            data: {
                'categoria': categoria,
                'cantidad_repeticion': cantidad_repeticion,
                'ancho': ancho,
                'alto': alto,
                'separacion': separacion,
                'algoritmo': algoritmo // Envía el algoritmo actual
            },
            headers: {
                'X-CSRFToken': getCookie('csrftoken')  // Obtén el CSRF token de las cookies
            },
            success: function (response) {

                // Actualiza el select de productos con la respuesta
                var productos = response.productos;
                var productoSelect = $('#producto');
                productoSelect.empty();  // Limpia las opciones actuales
                productos.forEach(function (producto) {
                    productoSelect.append(new Option(producto.nombre, producto.id));
                });

                // Actualiza el gráfico
                imgElement.src = response.grafico_url; // Carga el nuevo gráfico

                // Actualiza los valores de resultados en el DOM
                document.getElementById('cant_hojas').innerText = response.cantidad_hojas;
                document.getElementById('area_ocupada').innerText = response.area_ocupada;
                document.getElementById('cant_resultado').innerText = response.cant_elementos_empaquetados;

                // Mostrar el bloque del gráfico
                $('#grafico_contenedor').removeClass('hidden');
            },
            error: function (xhr, errmsg, err) {
                console.log('Error al generar gráfico:', xhr.status + ": " + xhr.responseText);  // Añadido
            }
        });
    }
    //Escucha del evento de cambio de categoría para generar el gráfico. Primero chequea que algoritmo es el corresponde y luego genera el gráfico.
    $('#categoria').change(function () {
        let algoritmoActual = $('#btn-regenerar').data('algoritmo');
        generarGrafico(algoritmoActual);
    });
    //Botón que permite regenerar el gráfico utilizando el algoritmo MaxRects o Guillotine
    $('#btn-regenerar').click(function (event) {
        event.preventDefault();  // Evita cualquier comportamiento predeterminado

        
        let algoritmoActual = $(this).data('algoritmo');
        let nuevoAlgoritmo = algoritmoActual === 'Guillotine' ? 'MaxRects' : 'Guillotine';
    
    
        let nuevoTooltip = algoritmoActual === 'Guillotine' 
            ? "Volver a graficar priorizando el posterior corte de la hoja" 
            : "Volver a graficar priorizando la cantidad de elementos que caben";
    
        let nuevoIcono = nuevoAlgoritmo === 'Guillotine' 
            ? '<i class="fa-solid fa-cubes-stacked"></i>' 
            : '<i class="fa-solid fa-scissors"></i>';
    
        // Actualiza el botón
        $(this).data('algoritmo', nuevoAlgoritmo); // Actualiza el algoritmo
        $(this).attr('title', nuevoTooltip).tooltip('show'); // Actualiza el tooltip
        $(this).find('i').replaceWith(nuevoIcono); // Cambia el ícono en el botón
    
        // Confirmar que se está invocando generarGrafico
        generarGrafico(nuevoAlgoritmo); // Regenera el gráfico con el nuevo algoritmo
    });
});



function enviarCantidadHojas() {
    const cantHojas = document.getElementById('cant_hojas').innerText;
    document.getElementById('cantidad_area').value = cantHojas;  // Completa el input de cantidad_area

    filtrarProductos(cantHojas)
}

function enviarAreaOcupada() {
    const areaOcupada = document.getElementById('area_ocupada').innerText;
    document.getElementById('cantidad_area').value = areaOcupada;
}


function filtrarProductos(cantidadHojas) {
    const rango = obtenerRango(cantidadHojas);
    const productoSelect = $('#producto');

    // Obtén todos los productos del select
    const productos = [];
    productoSelect.find('option').each(function() {
        productos.push({
            id: $(this).val(), // ID del producto
            nombre: $(this).text() // Nombre del producto
        });
    });

    // Filtra los productos basados en el rango
    const productosFiltrados = productos.filter(function (producto) {
        return producto.nombre.includes(rango);
    });

    if (productosFiltrados.length !== 0) {
        // Actualiza el select con los productos filtrados
        productoSelect.empty(); // Limpia las opciones actuales
        productosFiltrados.forEach(function (producto) {
            productoSelect.append(new Option(producto.nombre, producto.id));
        });

    };
}
function obtenerRango(cantidadHojas) {
    if (cantidadHojas >= 1 && cantidadHojas <= 29) {
        return '1-29';
    } else if (cantidadHojas >= 30 && cantidadHojas <= 100) {
        return '30-100';
    } else if (cantidadHojas >= 101) {
        return '101+';
    }
    return '';
}