from ia.anonimizador import anonimizar


def test_quita_correo_telefono_y_documento():
    r = anonimizar("Escribir a ana.gomez@uniminuto.edu.co o al 310 555 1234, cédula 1.023.456.789")
    assert "@" not in r.texto
    assert "310" not in r.texto
    assert "1.023.456.789" not in r.texto
    assert set(r.eliminados) == {"correo", "telefono", "documento"}


def test_quita_nombre_por_frase_de_presentacion():
    r = anonimizar("Mi nombre es Laura Martínez y perdí un termo")
    assert "Laura" not in r.texto and "Martínez" not in r.texto
    assert "termo" in r.texto
    assert r.eliminados == ["nombre"]


def test_quita_nombres_conocidos_sin_importar_tildes_ni_mayusculas():
    r = anonimizar("la billetera dice ANDRES perez adentro", nombres_conocidos=["Andrés Pérez"])
    assert "andres" not in r.texto.lower() and "perez" not in r.texto.lower()


def test_no_borra_marcas_ni_medidas():
    texto = "Termo Stanley de 1200 ml, es de Stanley y tiene sticker"
    r = anonimizar(texto)
    assert r.texto == texto
    assert r.eliminados == []


def test_nunca_devuelve_los_valores_eliminados():
    r = anonimizar("cel 3105551234")
    assert all("310" not in e for e in r.eliminados)
