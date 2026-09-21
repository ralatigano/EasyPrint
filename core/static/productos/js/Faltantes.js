// Vista de faltantes: consolida lo que falta de cada insumo en todos los
// pedidos, simula cuántos pedidos se cubren con una compra y arma la lista.
//
// La simulación reparte el material igual que el backend al registrar una
// compra (productos/stock.py → aplicar_ingreso): pedidos en orden de prioridad
// (fecha de entrega más cercana primero), cubriendo cada uno completo antes de
// pasar al siguiente. Los pedidos ya vienen ordenados así desde el servidor.
// Ese orden se puede alterar por pedido: "priorizar" lo manda al principio y
// "postergar" al final. Las elecciones se envían al registrar la compra para
// que el backend reparta igual que la simulación.

(function () {
    const datos = JSON.parse(document.getElementById("datos-faltantes").textContent);
    const hoy = JSON.parse(document.getElementById("fecha-hoy").textContent);
    if (!datos.length) return;

    const EPS = 1e-6;
    const porId = new Map(datos.map(i => [i.id, i]));

    // Estado de la simulación: seleccionado y unidades de compra por insumo.
    const estado = new Map(datos.map(i => [i.id, {
        seleccionado: false,
        comprar: sugerido(i),
    }]));

    // Prioridad manual por número de pedido: "priorizar" | "postergar".
    // Sin entrada = orden normal (por fecha).
    const prioridad = new Map();

    let dataTable = null;
    let filtroProveedor = "";   // "" = todos; id del proveedor o "sin"
    let insumoEnModal = null;

    // ─── Helpers ─────────────────────────────────────────────────────────────

    function sugerido(insumo) {
        return Math.max(Math.ceil((insumo.faltante - EPS) / insumo.factor), 0);
    }

    function num(valor, decimales = 2) {
        return Number(valor).toLocaleString("es-AR", { maximumFractionDigits: decimales });
    }

    function moneda(valor) {
        return "$ " + formatearNumeroLocal(valor);
    }

    function esc(texto) {
        const d = document.createElement("div");
        d.textContent = texto ?? "";
        return d.innerHTML;
    }

    function csrf() {
        return document.cookie.split("; ").find(r => r.startsWith("csrftoken="))?.split("=")[1] || "";
    }

    function claveProveedor(insumo) {
        return insumo.proveedor ? String(insumo.proveedor.id) : "sin";
    }

    function filas() {
        // Todas las filas, incluidas las ocultas por el filtro o la búsqueda.
        return dataTable ? dataTable.rows().nodes().toArray()
            : [...document.querySelectorAll("#Faltantes tbody tr[data-id]")];
    }

    function filasVisibles() {
        return dataTable ? dataTable.rows({ search: "applied" }).nodes().toArray() : filas();
    }

    function grupoPrioridad(numero) {
        const p = prioridad.get(numero);
        return p === "priorizar" ? 0 : p === "postergar" ? 2 : 1;
    }

    // Pedidos del insumo en el orden efectivo (sort estable: dentro de cada
    // grupo se conserva el orden por fecha que viene del servidor).
    function pedidosOrdenados(insumo) {
        return insumo.pedidos
            .map((p, idx) => ({ p, idx }))
            .sort((a, b) => grupoPrioridad(a.p.numero) - grupoPrioridad(b.p.numero) || a.idx - b.idx)
            .map(x => x.p);
    }

    // Reparte `unidades` de compra entre los pedidos del insumo, por prioridad.
    function asignar(insumo, unidades) {
        let disponible = unidades * insumo.factor;
        return pedidosOrdenados(insumo).map(p => {
            const cubre = Math.min(Math.max(disponible, 0), p.cantidad);
            disponible -= cubre;
            const completo = cubre >= p.cantidad - EPS;
            return { ...p, cubre, completo, parcial: !completo && cubre > EPS };
        });
    }

    function unidadesSimuladas(id, soloSeleccion) {
        const e = estado.get(id);
        if (soloSeleccion && !e.seleccionado) return 0;
        return e.comprar;
    }

    // Pedidos (con número) que quedan sin ningún faltante si se compra lo indicado.
    function pedidosDestrabados(soloSeleccion) {
        const bloqueados = new Set();
        const todos = new Set();
        for (const insumo of datos) {
            for (const a of asignar(insumo, unidadesSimuladas(insumo.id, soloSeleccion))) {
                if (a.numero === null) continue;
                todos.add(a.numero);
                if (!a.completo) bloqueados.add(a.numero);
            }
        }
        const destrabados = [...todos].filter(n => !bloqueados.has(n)).sort((a, b) => a - b);
        return { destrabados, total: todos.size };
    }

    function listasPrioridad() {
        const priorizados = [], postergados = [];
        prioridad.forEach((v, numero) => (v === "priorizar" ? priorizados : postergados).push(numero));
        return { priorizados, postergados };
    }

    // ─── Tabla ───────────────────────────────────────────────────────────────

    function contactoHTML(proveedor) {
        if (!proveedor) return '<span class="text-muted">—</span>';
        const iconos = [];
        if (proveedor.whatsapp) iconos.push(`<a href="https://wa.me/${proveedor.whatsapp}" target="_blank" rel="noopener" title="WhatsApp"><i class="fa-brands fa-whatsapp"></i></a>`);
        else if (proveedor.telefono) iconos.push(`<a href="tel:${esc(proveedor.telefono)}" title="${esc(proveedor.telefono)}"><i class="fa-solid fa-phone"></i></a>`);
        if (proveedor.email) iconos.push(`<a href="mailto:${esc(proveedor.email)}" title="${esc(proveedor.email)}"><i class="fa-regular fa-envelope"></i></a>`);
        if (proveedor.web) iconos.push(`<a href="${esc(proveedor.web)}" target="_blank" rel="noopener" title="Página web"><i class="fa-solid fa-globe"></i></a>`);
        return `${esc(proveedor.nombre)} <span class="ms-1">${iconos.join(" ")}</span>`;
    }

    function filaHTML(i) {
        const e = estado.get(i.id);
        return `
        <tr data-id="${i.id}">
            <td class="centered"><input type="checkbox" class="form-check-input chk-insumo" ${e.seleccionado ? "checked" : ""}></td>
            <td>${esc(i.nombre)}<div class="small text-muted">1 ${esc(i.unidad_compra)} = ${num(i.factor)} ${esc(i.unidad_uso)}</div></td>
            <td>${contactoHTML(i.proveedor)}</td>
            <td data-order="${i.faltante}">${num(i.faltante)} ${esc(i.unidad_uso)}</td>
            <td data-order="${sugerido(i)}">${num(sugerido(i))} ${esc(i.unidad_compra)}</td>
            <td><input type="number" min="0" step="1" class="form-control form-control-sm input-comprar" value="${e.comprar}"></td>
            <td class="cubre"></td>
            <td class="costo text-end"></td>
            <td class="text-nowrap">
                <button type="button" class="btn btn-dark btn-xs btn-pedidos" title="Ver los pedidos que necesitan este insumo y elegir cuáles cubrir">
                    <i class="fa-solid fa-clipboard-list"></i> ${i.pedidos.length}
                </button>
                <button type="button" class="btn btn-dark btn-xs btn-registrar" title="Registrar la compra de este insumo">
                    <i class="fa-solid fa-box-open"></i>
                </button>
            </td>
        </tr>`;
    }

    function actualizarFila(tr) {
        const insumo = porId.get(Number(tr.dataset.id));
        const e = estado.get(insumo.id);
        const asignacion = asignar(insumo, e.comprar);
        const completos = asignacion.filter(a => a.completo).length;
        const cubierto = asignacion.reduce((s, a) => s + a.cubre, 0);
        const pct = insumo.faltante > 0 ? Math.min(100, cubierto / insumo.faltante * 100) : 100;
        const color = completos === asignacion.length ? "bg-success" : (cubierto > EPS ? "bg-warning" : "bg-danger");
        const manual = insumo.pedidos.some(p => prioridad.has(p.numero));

        tr.querySelector(".cubre").innerHTML = `
            <div class="small">${completos} de ${asignacion.length} pedido${asignacion.length === 1 ? "" : "s"}${manual ? ' <i class="fa-solid fa-arrow-down-short-wide text-primary" title="Con prioridades elegidas a mano"></i>' : ""}</div>
            <div class="progress" role="progressbar" aria-valuenow="${pct.toFixed(0)}" aria-valuemin="0" aria-valuemax="100">
                <div class="progress-bar ${color}" style="width: ${pct}%"></div>
            </div>`;
        // No pisar el input mientras se está escribiendo en él.
        const input = tr.querySelector(".input-comprar");
        if (document.activeElement !== input) input.value = e.comprar;
        tr.querySelector(".costo").textContent = moneda(e.comprar * insumo.precio);
        tr.querySelector(".chk-insumo").checked = e.seleccionado;
        tr.classList.toggle("fila-seleccionada", e.seleccionado);
    }

    // Fila de total: suma lo visible. Si hay filas marcadas, solo esas.
    function actualizarTotal() {
        const visibles = filasVisibles().map(tr => porId.get(Number(tr.dataset.id)));
        const marcadas = visibles.filter(i => estado.get(i.id).seleccionado);
        const base = marcadas.length ? marcadas : visibles;
        const total = base.reduce((s, i) => s + estado.get(i.id).comprar * i.precio, 0);

        const partes = [];
        if (filtroProveedor) {
            const opcion = document.querySelector(`#filtroProveedor option[value="${filtroProveedor}"]`);
            partes.push(opcion ? opcion.textContent : "proveedor");
        } else if (visibles.length < datos.length) {
            partes.push("visibles");
        }
        if (marcadas.length) partes.push("seleccionados");
        const etiqueta = partes.length ? `Total (${partes.join(" · ")})` : "Total";
        document.getElementById("totalEtiqueta").textContent = etiqueta + ":";
        document.getElementById("totalMonto").textContent = moneda(total);
    }

    function actualizarResumen() {
        const seleccion = datos.filter(i => estado.get(i.id).seleccionado);
        const costo = seleccion.reduce((s, i) => s + estado.get(i.id).comprar * i.precio, 0);
        const resumen = document.getElementById("resumenSeleccion");
        const detalle = document.getElementById("resumenPedidos");

        document.getElementById("btnListaCompra").disabled = !seleccion.length;
        document.getElementById("btnRegistrarSeleccion").disabled = !seleccion.length;

        const { priorizados, postergados } = listasPrioridad();
        const cajaPrioridades = document.getElementById("resumenPrioridades");
        cajaPrioridades.classList.toggle("d-none", !priorizados.length && !postergados.length);
        const partes = [];
        if (priorizados.length) partes.push(`priorizados ${priorizados.map(n => "#" + n).join(", ")}`);
        if (postergados.length) partes.push(`postergados ${postergados.map(n => "#" + n).join(", ")}`);
        document.getElementById("resumenPrioridadesTexto").textContent = "Orden manual: " + partes.join(" · ") + ".";

        const { destrabados, total } = pedidosDestrabados(true);
        if (!seleccion.length) {
            resumen.textContent = "Ningún insumo seleccionado";
            detalle.textContent = `Hay ${total} pedido${total === 1 ? "" : "s"} esperando insumos. Seleccioná qué comprar para ver cuáles se destraban.`;
            return;
        }
        resumen.textContent = `${seleccion.length} insumo${seleccion.length === 1 ? "" : "s"} seleccionado${seleccion.length === 1 ? "" : "s"} · Costo estimado ${moneda(costo)}`;
        detalle.innerHTML = destrabados.length
            ? `Con esta compra se destraban <strong>${destrabados.length} de ${total}</strong> pedidos: ${destrabados.map(n => "#" + n).join(", ")}.`
            : `Con esta compra no se completa ningún pedido (de ${total}): a todos les sigue faltando algún insumo.`;
    }

    function actualizarTodo() {
        filas().forEach(actualizarFila);
        actualizarResumen();
        actualizarTotal();
        const visibles = filasVisibles().map(tr => estado.get(Number(tr.dataset.id)));
        const todos = document.getElementById("chkTodos");
        todos.checked = visibles.length > 0 && visibles.every(e => e.seleccionado);
        todos.indeterminate = !todos.checked && visibles.some(e => e.seleccionado);
    }

    // ─── Modal de pedidos (con prioridad manual) ─────────────────────────────

    function renderModalPedidos() {
        const insumo = insumoEnModal;
        const comprar = estado.get(insumo.id).comprar;
        const asignacion = asignar(insumo, comprar);
        document.getElementById("modalPedidosInsumoLabel").textContent = `Pedidos que necesitan ${insumo.nombre}`;
        document.getElementById("modalPedidosInsumoAyuda").textContent =
            `En el orden en que se cubren: primero la fecha de entrega más cercana, salvo que priorices o postergues ` +
            `un pedido (la elección vale para todos sus insumos). "Con la compra" usa la cantidad indicada en la tabla: ` +
            `${num(comprar)} ${insumo.unidad_compra} = ${num(comprar * insumo.factor)} ${insumo.unidad_uso}.`;

        document.getElementById("modalPedidosInsumoBody").innerHTML = asignacion.map((a, idx) => {
            const otros = a.numero === null ? [] : datos
                .filter(i => i.id !== insumo.id && i.pedidos.some(p => p.numero === a.numero))
                .map(i => i.nombre);
            const badge = a.completo
                ? '<span class="badge bg-success">Cubierto</span>'
                : a.parcial
                    ? `<span class="badge bg-warning text-dark">Parcial (${num(a.cubre)})</span>`
                    : '<span class="badge bg-danger">Sin cubrir</span>';
            const valor = prioridad.get(a.numero) || "";
            const selector = a.numero === null ? "—" : `
                <select class="form-select form-select-sm select-prioridad" data-numero="${a.numero}">
                    <option value="" ${valor === "" ? "selected" : ""}>Normal</option>
                    <option value="priorizar" ${valor === "priorizar" ? "selected" : ""}>Priorizar</option>
                    <option value="postergar" ${valor === "postergar" ? "selected" : ""}>Postergar</option>
                </select>`;
            return `
            <tr class="${valor === "postergar" ? "text-muted" : ""}">
                <td>${idx + 1}</td>
                <td>${a.numero === null ? '<span class="text-muted">Sin pedido</span>' : "#" + a.numero}</td>
                <td>${esc(a.cliente) || "—"}</td>
                <td>${esc(a.fecha_entrega) || "—"}</td>
                <td>${esc(a.estado) || "—"}</td>
                <td class="text-end text-nowrap">${num(a.cantidad)} ${esc(insumo.unidad_uso)}</td>
                <td>${badge}</td>
                <td>${selector}</td>
                <td class="small">${otros.length ? otros.map(esc).join(", ") : '<span class="text-muted">Nada más</span>'}</td>
            </tr>`;
        }).join("");

        const justo = unidadesParaNoPostergados(insumo);
        document.getElementById("btnAjustarComprarTexto").textContent =
            `Ajustar "A comprar" a ${num(justo)} ${insumo.unidad_compra}`;
    }

    // Unidades de compra justas para cubrir los pedidos no postergados.
    function unidadesParaNoPostergados(insumo) {
        const necesario = insumo.pedidos
            .filter(p => prioridad.get(p.numero) !== "postergar")
            .reduce((s, p) => s + p.cantidad, 0);
        return Math.max(Math.ceil((necesario - EPS) / insumo.factor), 0);
    }

    function abrirPedidos(insumo) {
        insumoEnModal = insumo;
        renderModalPedidos();
        bootstrap.Modal.getOrCreateInstance(document.getElementById("modalPedidosInsumo")).show();
    }

    // ─── Lista de compra ─────────────────────────────────────────────────────

    function itemsSeleccionados() {
        return datos
            .filter(i => estado.get(i.id).seleccionado && estado.get(i.id).comprar > 0)
            .map(i => ({ insumo: i, unidades: estado.get(i.id).comprar }));
    }

    function agruparPorProveedor(items) {
        const grupos = new Map();
        for (const it of items) {
            const clave = it.insumo.proveedor ? it.insumo.proveedor.nombre : "Sin proveedor";
            if (!grupos.has(clave)) grupos.set(clave, { proveedor: it.insumo.proveedor, items: [] });
            grupos.get(clave).items.push(it);
        }
        return [...grupos.entries()].sort(([a], [b]) =>
            a === "Sin proveedor" ? 1 : b === "Sin proveedor" ? -1 : a.localeCompare(b));
    }

    function lineas(items) {
        return items.map(it => `• ${num(it.unidades)} ${it.insumo.unidad_compra} – ${it.insumo.nombre}`);
    }

    function abrirListaCompra() {
        const items = itemsSeleccionados();
        if (!items.length) {
            alert("Los insumos seleccionados tienen 0 unidades a comprar.");
            return;
        }
        const grupos = agruparPorProveedor(items);
        const total = items.reduce((s, it) => s + it.unidades * it.insumo.precio, 0);

        const texto = [`Lista de compra – ${hoy}`, ""];
        for (const [nombre, g] of grupos) {
            texto.push(`*${nombre}*`, ...lineas(g.items), "");
        }
        texto.push(`Total estimado: ${moneda(total)}`);
        document.getElementById("textoListaCompra").value = texto.join("\n");

        // Mensaje listo para mandarle a cada proveedor (sin precios internos).
        const contactos = grupos.filter(([, g]) => g.proveedor && (g.proveedor.whatsapp || g.proveedor.email));
        document.getElementById("contactosProveedores").innerHTML = contactos.length
            ? `<div class="fw-bold mb-1">Enviar el pedido a cada proveedor:</div>` + contactos.map(([nombre, g]) => {
                const mensaje = ["Hola! Quería hacer el siguiente pedido:", ...lineas(g.items), "", "Gracias!"].join("\n");
                const botones = [];
                if (g.proveedor.whatsapp) {
                    botones.push(`<a class="btn btn-success btn-xs" target="_blank" rel="noopener" href="https://wa.me/${g.proveedor.whatsapp}?text=${encodeURIComponent(mensaje)}"><i class="fa-brands fa-whatsapp"></i> WhatsApp</a>`);
                }
                if (g.proveedor.email) {
                    botones.push(`<a class="btn btn-dark btn-xs" href="mailto:${esc(g.proveedor.email)}?subject=${encodeURIComponent("Pedido EasyPrint")}&body=${encodeURIComponent(mensaje)}"><i class="fa-regular fa-envelope"></i> Correo</a>`);
                }
                return `<div class="contacto-proveedor d-flex flex-wrap align-items-center gap-2 mb-1"><span>${esc(nombre)}:</span>${botones.join("")}</div>`;
            }).join("")
            : "";

        bootstrap.Modal.getOrCreateInstance(document.getElementById("modalListaCompra")).show();
    }

    async function copiarLista() {
        const area = document.getElementById("textoListaCompra");
        const boton = document.getElementById("btnCopiarLista");
        try {
            await navigator.clipboard.writeText(area.value);
        } catch {
            area.select();
            document.execCommand("copy");
        }
        const original = boton.innerHTML;
        boton.innerHTML = '<i class="fa-solid fa-check"></i> Copiado';
        setTimeout(() => boton.innerHTML = original, 1500);
    }

    function descargarExcel() {
        const items = itemsSeleccionados().map(it => ({ id: it.insumo.id, unidades: it.unidades }));
        document.getElementById("formListaExcelItems").value = JSON.stringify(items);
        document.getElementById("formListaExcel").submit();
    }

    // ─── Registrar compra ────────────────────────────────────────────────────

    function abrirRegistrarCompra(insumos) {
        document.getElementById("registrarCompraBody").innerHTML = insumos.map(i => `
            <tr data-id="${i.id}">
                <td>${esc(i.nombre)}</td>
                <td><input type="number" min="0" step="1" class="form-control form-control-sm input-recibido" value="${estado.get(i.id).comprar}"></td>
                <td>${esc(i.unidad_compra)}</td>
                <td class="small text-muted equivale"></td>
            </tr>`).join("");
        document.querySelectorAll("#registrarCompraBody tr").forEach(actualizarEquivalencia);

        const aviso = document.getElementById("registrarCompraPrioridades");
        const texto = document.getElementById("resumenPrioridadesTexto").textContent;
        aviso.classList.toggle("d-none", prioridad.size === 0);
        aviso.textContent = prioridad.size ? `Se respeta el ${texto.charAt(0).toLowerCase()}${texto.slice(1)}` : "";

        bootstrap.Modal.getOrCreateInstance(document.getElementById("modalRegistrarCompra")).show();
    }

    function actualizarEquivalencia(tr) {
        const insumo = porId.get(Number(tr.dataset.id));
        const unidades = Math.max(Number(tr.querySelector(".input-recibido").value) || 0, 0);
        tr.querySelector(".equivale").textContent = `${num(unidades * insumo.factor)} ${insumo.unidad_uso} (faltan ${num(insumo.faltante)})`;
    }

    async function confirmarCompra() {
        const items = [...document.querySelectorAll("#registrarCompraBody tr")]
            .map(tr => ({ id: Number(tr.dataset.id), unidades: Number(tr.querySelector(".input-recibido").value) || 0 }))
            .filter(it => it.unidades > 0);
        if (!items.length) {
            alert("Indicá al menos una cantidad mayor a 0.");
            return;
        }
        const boton = document.getElementById("btnConfirmarCompra");
        boton.disabled = true;
        try {
            const res = await fetch("/productos/insumos/registrarCompra/", {
                method: "POST",
                headers: { "X-CSRFToken": csrf(), "Content-Type": "application/json" },
                body: JSON.stringify({ items, ...listasPrioridad() }),
            });
            const data = await res.json();
            if (!data.ok) {
                alert(data.mensaje);
                boton.disabled = false;
                return;
            }
            // El mensaje de éxito llega como mensaje de Django al recargar.
            location.reload();
        } catch (err) {
            console.error("Error al registrar compra:", err);
            alert("Error de conexión al registrar la compra. Intentá nuevamente.");
            boton.disabled = false;
        }
    }

    // ─── Inicialización ──────────────────────────────────────────────────────

    const tbody = document.querySelector("#Faltantes tbody");
    tbody.innerHTML = datos.map(filaHTML).join("");

    // Proveedores presentes en los faltantes, para el filtro.
    const selectProv = document.getElementById("filtroProveedor");
    const provs = new Map();
    datos.forEach(i => provs.set(claveProveedor(i), i.proveedor ? i.proveedor.nombre : "Sin proveedor"));
    [...provs.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([id, nombre]) => {
        selectProv.insertAdjacentHTML("beforeend", `<option value="${id}">${esc(nombre)}</option>`);
    });

    // Filtro por proveedor como búsqueda adicional de DataTables.
    $.fn.dataTable.ext.search.push((settings, _data, dataIndex) => {
        if (settings.nTable.id !== "Faltantes" || !filtroProveedor) return true;
        const tr = settings.aoData[dataIndex].nTr;
        return claveProveedor(porId.get(Number(tr.dataset.id))) === filtroProveedor;
    });

    window.addEventListener("load", () => {
        dataTable = $("#Faltantes").DataTable({
            paging: false,
            info: false,
            order: [[1, "asc"]],
            columnDefs: [{ orderable: false, targets: [0, 5, 6, 7, 8] }],
            language: {
                zeroRecords: "No hay insumos que coincidan con la búsqueda",
                search: "Buscar:",
            },
        });
        // La búsqueda de texto también cambia lo visible: recalcular total y "todos".
        dataTable.on("draw", actualizarTodo);
        document.getElementById("nav_item_insumos").style.fontWeight = "bold";
        actualizarTodo();
    });

    tbody.addEventListener("change", (ev) => {
        if (!ev.target.classList.contains("chk-insumo")) return;
        const tr = ev.target.closest("tr[data-id]");
        estado.get(Number(tr.dataset.id)).seleccionado = ev.target.checked;
        actualizarTodo();
    });

    tbody.addEventListener("input", (ev) => {
        if (!ev.target.classList.contains("input-comprar")) return;
        const tr = ev.target.closest("tr[data-id]");
        estado.get(Number(tr.dataset.id)).comprar = Math.max(Number(ev.target.value) || 0, 0);
        actualizarFila(tr);
        actualizarResumen();
        actualizarTotal();
    });

    tbody.addEventListener("click", (ev) => {
        const tr = ev.target.closest("tr[data-id]");
        if (!tr) return;
        const insumo = porId.get(Number(tr.dataset.id));
        if (ev.target.closest(".btn-pedidos")) abrirPedidos(insumo);
        if (ev.target.closest(".btn-registrar")) abrirRegistrarCompra([insumo]);
    });

    document.getElementById("chkTodos").addEventListener("change", (ev) => {
        // Solo afecta a las filas visibles (respeta búsqueda y filtro de proveedor).
        filasVisibles().forEach(tr => {
            estado.get(Number(tr.dataset.id)).seleccionado = ev.target.checked;
        });
        actualizarTodo();
    });

    // Filtrar por proveedor: oculta el resto y deja seleccionadas solo sus filas.
    selectProv.addEventListener("change", () => {
        filtroProveedor = selectProv.value;
        if (filtroProveedor) {
            datos.forEach(i => {
                estado.get(i.id).seleccionado = claveProveedor(i) === filtroProveedor;
            });
        }
        dataTable.draw();   // dispara actualizarTodo
    });

    document.getElementById("modalPedidosInsumoBody").addEventListener("change", (ev) => {
        const select = ev.target.closest(".select-prioridad");
        if (!select) return;
        const numero = Number(select.dataset.numero);
        if (select.value) prioridad.set(numero, select.value);
        else prioridad.delete(numero);
        renderModalPedidos();
        actualizarTodo();
    });

    document.getElementById("btnAjustarComprar").addEventListener("click", () => {
        if (!insumoEnModal) return;
        estado.get(insumoEnModal.id).comprar = unidadesParaNoPostergados(insumoEnModal);
        renderModalPedidos();
        actualizarTodo();
    });

    document.getElementById("btnRestablecerPrioridades").addEventListener("click", () => {
        prioridad.clear();
        actualizarTodo();
    });

    document.getElementById("btnListaCompra").addEventListener("click", abrirListaCompra);
    document.getElementById("btnCopiarLista").addEventListener("click", copiarLista);
    document.getElementById("btnExcelLista").addEventListener("click", descargarExcel);
    document.getElementById("btnRegistrarSeleccion").addEventListener("click", () => {
        abrirRegistrarCompra(datos.filter(i => estado.get(i.id).seleccionado));
    });
    document.getElementById("registrarCompraBody").addEventListener("input", (ev) => {
        const tr = ev.target.closest("tr[data-id]");
        if (tr) actualizarEquivalencia(tr);
    });
    document.getElementById("btnConfirmarCompra").addEventListener("click", confirmarCompra);
})();
