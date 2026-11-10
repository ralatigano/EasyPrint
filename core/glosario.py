"""Explicaciones en criollo de los conceptos de la estructura de costos.

Fuente única de los textos que muestran los botones "(i)" de la UI. Están acá
y no sueltos en cada template porque varios conceptos (la tasa por hora, los
dos pisos) aparecen en más de una pantalla, y no sirve de nada que cada una
los explique distinto.

Se usan con el tag `{% ayuda 'clave' %}` (ver core/templatetags/ayuda.py).

Al escribirlos: en castellano llano y en segunda persona, sin fórmulas salvo
que aclaren, y diciendo para qué sirve el número, no solo qué es. Van dentro
de un tooltip, así que conviene que no pasen de unas tres líneas.
"""

GLOSARIO = {

    # ── Panel de la tasa ──────────────────────────────────────────────────
    'costo_fijo_mensual': (
        'Lo que te sale tener el negocio abierto un mes, aunque entre o '
        'no entre trabajo: alquiler, sueldos, luz, impuestos, las cuotas '
        'de las máquinas. Es la suma de la tabla de costos fijos de abajo.'
    ),
    'horas_disponibles': (
        'Las horas que pagás en el mes: operarios × horas al día × días al '
        'mes. Es el total teórico, antes de descontar el tiempo que no se '
        'está produciendo.'
    ),
    'horas_productivas': (
        'De las horas que pagás, las que realmente se van en producir (el '
        'resto se va en atender, comprar, limpiar y tiempos muertos). Estas '
        'son las horas que cuentan para cubrir el costo fijo.'
    ),
    'tasa_hora': (
        'Cuánto tiene que aportar cada hora de trabajo para cubrir la '
        'estructura: costo fijo mensual ÷ horas productivas. '
    ),

    # ── Capacidad productiva ──────────────────────────────────────────────
    'operarios': (
        'Cuántas personas producen. No cuentes administración ni ventas: acá '
        'van solo las que hacen el trabajo.'
    ),
    'horas_dia': 'Cuántas horas trabaja cada operario por día.',
    'dias_mes': (
        'Cuántos días se trabaja al mes. Suelen ser 22 si trabajás de lunes a '
        'viernes.'
    ),
    'ratio_productivas': (
        'Qué parte de las horas que pagás se dedica de verdad a producir, de '
        '0 a 1. Si ponés 0,70, de cada 10 horas 7 son de producción y 3 se '
        'van en otra cosa. Cuanto más bajo, más sube la tasa por hora.'
    ),
    'margen_objetivo': (
        'La ganancia que querés sobre el costo total (material + estructura) '
        'en el método nuevo. 1,30 es cobrar un 30% por encima del costo. Ojo: '
        'no es lo mismo que el "factor" del producto, que multiplica solo el '
        'material.'
    ),
    'horas_legacy': (
        'Las horas de mano de obra que usa el método viejo, que es el que hoy '
        'define lo que cobrás. Está en 1,00 para que el precio no se mueva '
        'mientras cargás los tiempos reales de cada producto. '
    ),

    # ── Costos fijos (tabla) ──────────────────────────────────────────────
    'grupo_costo': (
        'Etiqueta libre para ordenar la lista (Ocupación, Sueldos, '
        'Impuestos…). No afecta ningún cálculo.'
    ),
    'periodicidad': (
        'Cada cuánto pagás ese gasto. El sistema lo lleva a su equivalente '
        'mensual, así que podés cargarlo como te llega la factura.'
    ),
    'meses_amortizacion': (
        'Solo para los gastos de periodicidad "Único": en cuántos meses '
        'repartís una compra puntual. Ejemplo: un plotter de $2.400.000 en 24 '
        'meses son $100.000 por mes.'
    ),
    'costo_mensual_linea': (
        'Lo que esa línea aporta por mes al costo fijo, ya normalizada. Es lo '
        'que termina usando la tasa por hora. Se calcula solo.'
    ),

    # ── Modal de resultado al cotizar ─────────────────────────────────────
    'comparacion_metodos': (
        'Compara lo que cobrás hoy contra lo que daría calcular el precio con '
        'la estructura de costos. Es informativo: no cambia el precio, salvo '
        'que uses el botón "Agregar con precio sugerido".'
    ),
    'precio_actual': (
        'Lo que cobra el método de siempre: el material multiplicado por el '
        'factor del producto, más la mano de obra y el empaquetado. Es el '
        'precio que se va a cargar si apretás "Agregar".'
    ),
    'precio_sugerido': (
        'Lo que convendría cobrar según la estructura: el costo real del '
        'trabajo (material + las horas que ocupa) más el margen objetivo.'
    ),
    'diferencia_metodos': (
        'Cuánto está por encima (+) o por debajo (−) el precio sugerido '
        'respecto del que cobrás hoy. +20% significa que el sugerido es un '
        '20% más caro que tu precio actual.'
    ),
    'descuento_margen': (
        'Hasta dónde podés bajar el precio. Mientras no cruces el piso de '
        'absorción seguís ganando (menos) y el trabajo sigue pagando su '
        'parte de los gastos fijos. Entre ese piso y el absoluto no ganás: '
        'recuperás el material y solo una parte de la estructura, así que '
        'sirve para un caso puntual, no como norma. Debajo del piso '
        'absoluto, ponés plata de tu bolsillo.'
    ),
    'piso_absoluto': (
        'Lo que te cuesta este trabajo en material y empaquetado, sin nada '
        'más. Por debajo de este precio perdés plata en el acto. '
    ),
    'piso_absorcion': (
        'El material más la parte de los gastos fijos que le toca a este '
        'trabajo según las horas que ocupa. A este precio no ganás nada, pero '
        'cubrís el costo real. Entre este piso y el absoluto estás ayudando a '
        'pagar la estructura, aunque no ganes.'
    ),
    'tasa_hora_usada': (
        'La tasa por hora con la que se calculó este trabajo, tomada de la '
        'estructura de costos. Se configura en Configuración → Estructura de '
        'costos.'
    ),
    'tiempo_produccion': (
        'Cuánto se estima que tarda este trabajo. Es lo que determina qué '
        'parte de los gastos fijos absorbe, a razón de la tasa por hora.'
    ),

    # ── Dashboard ─────────────────────────────────────────────────────────
    'punto_equilibrio': (
        'Cuántas horas de producción tenés que vender este mes para cubrir '
        'los gastos fijos. Sale de dividir el costo fijo por lo que deja en '
        'promedio cada hora vendida. Por debajo de esa marca, el mes da '
        'pérdida.'
    ),
    'horas_vendidas_mes': (
        'Las horas de producción de los trabajos que este mes pasaron de '
        'presupuesto a pedido. Solo cuenta lo cotizado con la estructura de '
        'costos: lo cotizado antes no tiene el dato y falsearía el panel.'
    ),
    'horas_objetivo': (
        'Las horas productivas que da tu capacidad declarada en el mes '
        '(operarios × horas × días × ratio). Es el techo contra el que se '
        'mide lo que se vendió.'
    ),
    'absorcion_mes': (
        'Cuánto de los gastos fijos del mes recuperaste con las horas '
        'vendidas. En verde ya los cubriste; en rojo todavía falta. Es un '
        'mecanismo de precios, no un flujo de fondos: el alquiler y los '
        'sueldos se pagan igual. Un mes en rojo no es alarma (hay '
        'estacionalidad); varios seguidos sí.'
    ),
    'absorcion_recuperada': (
        'Las horas vendidas por la tasa por hora: la parte de los gastos '
        'fijos que esos trabajos ya pagaron.'
    ),
    'conversion_cotizado': (
        'Qué proporción de las horas que cotizaste terminó vendida. Mide '
        'cuánto de lo que presupuestás se convierte en trabajo real.'
    ),
    'contribucion_por_hora': (
        'Lo que deja cada hora de ese producto después de pagar su material. '
        'Es el criterio para saber qué conviene fomentar: el recurso escaso es '
        'el tiempo, así que un producto de margen chico pero rápido puede '
        'rendir más que uno de margen grande que tarda un día.'
    ),
}
