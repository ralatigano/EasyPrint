from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from .models import Categoria, Insumo, Producto, ComponenteProducto


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def crear_usuario_gerencia(username="gerente"):
    user = User.objects.create_user(username=username, password="test1234")
    grupo, _ = Group.objects.get_or_create(name="Gerencia")
    user.groups.add(grupo)
    return user


def crear_datos_base():
    cat = Categoria.objects.create(nombre="Papeles")
    insumo = Insumo.objects.create(
        nombre="Papel obra 80g",
        unidad_medida="resma",
        unidad_composicion="hoja",
        factor_conversion=500,
        precio=Decimal("10000"),
    )
    return cat, insumo


def log(msg):
    print(f"\n      {msg}")


# ---------------------------------------------------------------------------
# Tests: calculo de precio al guardar un producto
# ---------------------------------------------------------------------------

class PrecioProductoCalculadoTest(TestCase):
    """Grupo: calculo de precio al guardar un producto."""

    def setUp(self):
        self.client = Client()
        self.user = crear_usuario_gerencia()
        self.client.login(username="gerente", password="test1234")
        self.cat, self.insumo = crear_datos_base()

    def test_precio_se_calcula_desde_insumos(self):
        """El backend ignora productoPrecio=0 del front y calcula desde insumos."""
        precio_por_hoja = self.insumo.precio / self.insumo.factor_conversion
        log(f"Endpoint : POST /productos/guardarProducto")
        log(f"Insumo   : {self.insumo.nombre}")
        log(f"Precio   : ${self.insumo.precio} / {self.insumo.factor_conversion} hojas = ${precio_por_hoja} por hoja")
        log(f"Cantidad : 1 hoja")
        log(f"Front envia productoPrecio=0 (simula timing bug)")

        response = self.client.post("/productos/guardarProducto", {
            "id_producto": "0",
            "productoNombre": "Hoja A4",
            "productoCategoria": self.cat.id,
            "productoAncho": "21",
            "productoAlto": "29.7",
            "tercerizado": "",
            "productoMargen": "1",
            "productoPrecio": "0",
            "insumo_0_id": self.insumo.id,
            "insumo_0_cantidad": "1",
        })

        producto = Producto.objects.get(nombre="Hoja A4")
        esperado = Decimal("10000") / 500 * 1
        log(f"Resultado: precio almacenado = ${producto.precio} (esperado: ${esperado})")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(producto.precio, esperado)

    def test_precio_con_varios_insumos(self):
        """Con dos insumos el precio es la suma: papel ($20) + tinta ($10) = $30."""
        insumo2 = Insumo.objects.create(
            nombre="Tinta negra",
            unidad_medida="litro",
            unidad_composicion="ml",
            factor_conversion=1000,
            precio=Decimal("5000"),
        )
        pu1 = self.insumo.precio / self.insumo.factor_conversion
        pu2 = insumo2.precio / insumo2.factor_conversion
        log(f"Endpoint : POST /productos/guardarProducto")
        log(f"Insumo 1 : {self.insumo.nombre} x 1 = ${pu1}")
        log(f"Insumo 2 : {insumo2.nombre} x 2 = ${pu2 * 2}")
        log(f"Esperado : ${pu1 * 1 + pu2 * 2}")

        self.client.post("/productos/guardarProducto", {
            "id_producto": "0",
            "productoNombre": "Impresion A4",
            "productoCategoria": self.cat.id,
            "productoAncho": "21",
            "productoAlto": "29.7",
            "tercerizado": "",
            "productoMargen": "1",
            "productoPrecio": "9999",
            "insumo_0_id": self.insumo.id,
            "insumo_0_cantidad": "1",
            "insumo_1_id": insumo2.id,
            "insumo_1_cantidad": "2",
        })

        producto = Producto.objects.get(nombre="Impresion A4")
        log(f"Resultado: ${producto.precio}")
        self.assertEqual(producto.precio, Decimal("30"))

    def test_producto_tercerizado_precio_proveedor(self):
        """Tercerizado: precio=0, precio_proveedor=valor enviado."""
        log(f"Endpoint    : POST /productos/guardarProducto")
        log(f"Tercerizado : True | productoPrecio enviado: $1500")

        self.client.post("/productos/guardarProducto", {
            "id_producto": "0",
            "productoNombre": "Servicio externo",
            "productoCategoria": self.cat.id,
            "productoAncho": "0",
            "productoAlto": "0",
            "tercerizado": "on",
            "productoMargen": "1",
            "productoPrecio": "1500",
        })

        producto = Producto.objects.get(nombre="Servicio externo")
        log(f"Resultado   : precio={producto.precio}, precio_proveedor={producto.precio_proveedor}")
        self.assertEqual(producto.precio, Decimal("0"))
        self.assertEqual(producto.precio_proveedor, Decimal("1500"))


# ---------------------------------------------------------------------------
# Tests: deteccion automatica del tier segun cantidad de hojas
# ---------------------------------------------------------------------------

class ResolverTierTest(TestCase):
    """Grupo: deteccion automatica del tier correcto segun cantidad de hojas."""

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username="vendedor", password="test1234")
        self.client.login(username="vendedor", password="test1234")
        self.cat = Categoria.objects.create(nombre="Papeles")

        self.tier_1_5 = Producto.objects.create(
            nombre="Papel Obra [1-5]", categoria=self.cat,
            ancho=20, alto=30, precio=Decimal("100"),
        )
        self.tier_6_30 = Producto.objects.create(
            nombre="Papel Obra [6-30]", categoria=self.cat,
            ancho=20, alto=30, precio=Decimal("80"),
        )
        self.tier_31_inf = Producto.objects.create(
            nombre="Papel Obra [31-INF]", categoria=self.cat,
            ancho=20, alto=30, precio=Decimal("60"),
        )

    def _resolver(self, producto_id, cantidad):
        response = self.client.post("/productos/resolverTier", {
            "producto_id": producto_id,
            "cantidad": cantidad,
        })
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_cantidad_en_rango_1_5(self):
        """3 hojas -> debe quedarse en el tier (1-5)."""
        log(f"Endpoint : POST /productos/resolverTier")
        log(f"Familia  : 'Papel Obra' - tiers disponibles: (1-5) | (6-30) | (31-INF)")
        log(f"Cantidad : 3 hojas -> esperado: 'Papel Obra (1-5)'")

        data = self._resolver(self.tier_1_5.id, 3)
        log(f"Resultado: {data['nombre']} | tier_encontrado={data['tier_encontrado']}")

        self.assertTrue(data["tier_encontrado"])
        self.assertEqual(data["producto_id"], self.tier_1_5.id)

    def test_cantidad_en_limite_inferior_6_30(self):
        """6 hojas -> limite inferior exacto del tier (6-30)."""
        log(f"Endpoint : POST /productos/resolverTier")
        log(f"Cantidad : 6 hojas -> esperado: 'Papel Obra (6-30)' (limite inferior exacto)")

        data = self._resolver(self.tier_1_5.id, 6)
        log(f"Resultado: {data['nombre']} | tier_encontrado={data['tier_encontrado']}")

        self.assertTrue(data["tier_encontrado"])
        self.assertEqual(data["producto_id"], self.tier_6_30.id)

    def test_cantidad_en_limite_superior_6_30(self):
        """30 hojas -> limite superior exacto del tier (6-30)."""
        log(f"Endpoint : POST /productos/resolverTier")
        log(f"Cantidad : 30 hojas -> esperado: 'Papel Obra (6-30)' (limite superior exacto)")

        data = self._resolver(self.tier_1_5.id, 30)
        log(f"Resultado: {data['nombre']} | tier_encontrado={data['tier_encontrado']}")

        self.assertTrue(data["tier_encontrado"])
        self.assertEqual(data["producto_id"], self.tier_6_30.id)

    def test_cantidad_en_rango_infinito(self):
        """500 hojas -> debe caer en el tier (31-INF)."""
        log(f"Endpoint : POST /productos/resolverTier")
        log(f"Cantidad : 500 hojas -> esperado: 'Papel Obra (31-INF)'")

        data = self._resolver(self.tier_1_5.id, 500)
        log(f"Resultado: {data['nombre']} | tier_encontrado={data['tier_encontrado']}")

        self.assertTrue(data["tier_encontrado"])
        self.assertEqual(data["producto_id"], self.tier_31_inf.id)

    def test_producto_sin_rango_en_nombre(self):
        """Producto sin patron (N-M) -> tier_encontrado=False, devuelve el mismo producto."""
        prod = Producto.objects.create(
            nombre="Vinilo generico", categoria=self.cat,
            ancho=10, alto=10, precio=Decimal("50"),
        )
        log(f"Endpoint : POST /productos/resolverTier")
        log(f"Producto : '{prod.nombre}' (sin rango en el nombre)")
        log(f"Cantidad : 10 -> esperado: tier_encontrado=False")

        data = self._resolver(prod.id, 10)
        log(f"Resultado: {data['nombre']} | tier_encontrado={data['tier_encontrado']}")

        self.assertFalse(data["tier_encontrado"])
        self.assertEqual(data["producto_id"], prod.id)


# ---------------------------------------------------------------------------
# Tests: cambiar precio de insumo propaga a los productos que lo usan
# ---------------------------------------------------------------------------

class PropagacionPrecioInsumoTest(TestCase):
    """Grupo: cambiar el precio de un insumo actualiza los productos que lo usan."""

    def setUp(self):
        self.client = Client()
        self.user = crear_usuario_gerencia()
        self.client.login(username="gerente", password="test1234")

        cat = Categoria.objects.create(nombre="Test")
        self.insumo = Insumo.objects.create(
            nombre="Papel test",
            unidad_medida="resma",
            unidad_composicion="hoja",
            factor_conversion=100,
            precio=Decimal("1000"),
        )
        self.producto = Producto.objects.create(
            nombre="Hoja test", categoria=cat,
            precio=Decimal("10"),
        )
        ComponenteProducto.objects.create(
            producto=self.producto,
            insumo=self.insumo,
            cantidad=1,
        )

    def test_precio_producto_se_actualiza_al_cambiar_insumo(self):
        """Subir el precio del insumo de $1000 a $2000 actualiza el producto de $10 a $20."""
        log(f"Endpoint    : POST /productos/guardarInsumo/")
        log(f"Insumo      : {self.insumo.nombre}")
        log(f"Precio unit.: ${self.insumo.precio} / {self.insumo.factor_conversion} = ${self.insumo.precio / self.insumo.factor_conversion} por hoja")
        log(f"Producto    : '{self.producto.nombre}' usa 1 hoja -> precio actual: ${self.producto.precio}")
        log(f"Cambio      : precio del insumo $1000 -> $2000")
        log(f"Esperado    : precio del producto $10 -> $20")

        self.client.post("/productos/guardarInsumo/", {
            "id_insumo": self.insumo.id,
            "nombre": self.insumo.nombre,
            "unidad_medida": self.insumo.unidad_medida,
            "unidad_composicion": self.insumo.unidad_composicion,
            "factor_conversion": self.insumo.factor_conversion,
            "precio_unitario": "2000",
            "stock": "10",
            "activo": "on",
        })

        self.producto.refresh_from_db()
        log(f"Resultado   : precio del producto = ${self.producto.precio}")
        self.assertEqual(self.producto.precio, Decimal("20"))
