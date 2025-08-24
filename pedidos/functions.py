from datetime import datetime


def armar_numero_pedido():
    d = datetime.now()
    if d.month < 10:
        m = '0' + str(d.month)
    else:
        m = str(d.month)
    if d.day < 10:
        day = '0' + str(d.day)
    else:
        day = str(d.day)

    if d.hour < 10:
        h = '0' + str(d.hour)
    else:
        h = str(d.hour)
    if d.minute < 10:
        min = '0' + str(d.minute)
    else:
        min = str(d.minute)
    if d.second < 10:
        s = '0' + str(d.second)
    else:
        s = str(d.second)
    return f'{d.year}{m}{day}{h}{min}{s}'
