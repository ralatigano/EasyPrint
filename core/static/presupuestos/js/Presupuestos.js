
let dataTable;
let dataTableIsInitilized=false;

const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Presupuestos").DataTable({
        language: {
            lengthMenu: 'Mostrar _MENU_ presupuestos por página',
            zeroRecords: 'No hay presupuestos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ presupuestos',
            infoEmpty: 'No hay presupuestos',
            InfoFiltered: '(filtrado de _MAX_ presupuestos totales)',
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
    document.getElementById("nav_item_presupuestos").style.fontWeight = "bold";
});


