# Correcciones de Joaquín · Rat.IA Instagram

Reglas que salieron de mirar piezas reales. No son preferencias sueltas: cada
una tiene el caso que la provocó, para que no se "mejoren" de vuelta.

## 26-ago-2026 · El nombre del producto va RESUMIDO en la pieza

**Joaquín, textual:** *"tampoco es importante subir el nombre del producto
completo en la imagen (ej: no poner: audifonos inalambricos bluettoth 5.3 con
cancelacion de ruido. mejor resumirlo a: audifonos bluetooth cancelacion
ruido)"*.

**Por qué:** los títulos de retail están escritos para el buscador, no para
leerse. Puesto entero, el titular sale en 3 líneas, obliga a bajar el cuerpo
de la tipografía y le come el espacio al "¡70% OFF!", que es lo que para el
scroll. Con el nombre corto entra en una línea y el OFF queda grande —
comparar `assets/muestras/oferta_2k.png` (título largo) contra
`oferta_1k.png` (corto).

**Cómo se aplica:** `ratia_texto.nombre_corto()`, máximo 5 palabras, con
Haiku y respaldo determinista. **Sólo puede QUITAR palabras del título
original, nunca agregar** — un modelo que "completa" el nombre de un producto
es el mismo modo de falla del frasco inventado del 24-ago.

## 26-ago-2026 · El caption dice el COMERCIO, y nada de DM ni links

**Joaquín, textual:** *"la idea es que tambien se suba el caption con haiku
[…] y decir el comercio del cual fue o es la oferta. sin dm ni nada, ni dar
link, solo decir comercio"*.

Reemplaza al caption anterior ("comenta OFERTA y te paso el link por DM"): un
link saliente le baja el alcance al post y el flujo de DM todavía no existe.

**Cómo se aplica:** `ratia_texto.caption()`. Además de pedírselo al modelo hay
una **red de seguridad** que descarta el texto si trae `dm`, `link`, `http`,
`comenta`… La instrucción sola no es garantía.

## 26-ago-2026 · No inventar disponibilidad

Salió de una prueba: Haiku escribió *"anda a verificar si quedan stock"*. No
tenemos ese dato, y en un post automático se lee como si lo tuviéramos.

La red de seguridad rechaza `stock`, `quedan`, `agot`, `últimas unidades`,
`cuotas` y `despacho`. El caption habla SOLO del producto, su precio y el
comercio. (Para un error de precio sí se puede decir que puede corregirse:
eso es cierto por definición.)
