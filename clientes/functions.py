from .models import Cliente


def parsear_cliente(cliente_input):
    """
    Procesa el input del cliente y devuelve una instancia de Cliente.
    Maneja:
    - <id>|<referencia>
    - texto libre
    - vacío → Consumidor final
    """

    cliente_input = (cliente_input or "").strip()

    if not cliente_input:
        return Cliente.objects.get(nombre="Consumidor final")

    if "|" in cliente_input:
        posible_id = cliente_input.split("|", 1)[0].strip()

        if posible_id.isdigit():
            try:
                cliente = Cliente.objects.get(id=int(posible_id))
                cliente.frecuencia = (cliente.frecuencia or 0) + 1
                cliente.save()
                return cliente
            except Cliente.DoesNotExist:
                print(
                    f"[parsear_cliente] No se encontró cliente con ID {posible_id}. Se intentará como texto libre.")

    # Si no vino ID o no se encontró, tratamos como texto libre
    cliente = Cliente.objects.create(
        nombre=cliente_input,
        negocio=None,
        frecuencia=1
    )
    return cliente
