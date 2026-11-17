# Qué se hizo y qué falta

Fecha: 2026-11-14. Sigue la lista de 14 puntos que Juan Camilo le pasó a
Jefferson el 2026-11-13. El estado general del proyecto está en
[`OFICIAL.md`](OFICIAL.md), que manda sobre este archivo.

## Decisiones (Juan Camilo, 2026-11-14)

Son las que Jefferson dejó abiertas el 2026-11-13. Ya están tomadas.

| Decisión | Qué se decidió | Estado |
|---|---|---|
| Punto 10: acercar el protocolo a B.A.T.M.A.N. | **No se hace.** Queda como recomendación (ya estaba en `sec:recomendaciones`) | Cerrada |
| Punto 11: TCP con tiempo real | **No se rediseña `sim/datos.py`.** En su lugar, algo visual y sencillo: retardo estimado y línea de tiempo de cada paquete en la pestaña Tráfico | Hecho |
| Renombrar `rescatista_perdido` y `colapso_progresivo` | **No se renombran** | Cerrada |
| Captura de las capas del mapa con semilla fija | **Sí** | Hecho |
| Punto 5: defensa frente a ns-3 | **Aprobada** la propuesta de `VERIFICACION_FUENTES.md` (sección 1) | Cerrada; va a la sustentación (punto 14) |

## Reparto del resto

Mitad para Claude (con Juan Camilo, en su máquina Linux) y mitad para
Jefferson. La mitad de Claude es la de código, corridas y cifras; la de
Jefferson, la de lectura de fuentes y redacción.

### Claude: hecho el 2026-11-14

- **Punto 11, versión visual.** `sim/datos.py` estima el retardo de cada
  paquete entregado: 2 ms por intento de transmisión por radio
  (`T_INTENTO_RADIO`) y 1 s de espera antes de cada retransmisión de TCP
  (`RTO_TCP`, el mínimo de RFC 6298). UDP hasta que llega, ICMP ida y
  vuelta, TCP hasta que llega el segmento. No consume `random`: el lote
  `tipos_paquete` salió idéntico. La pestaña Tráfico muestra el retardo
  medio por tipo como barras y una línea de tiempo por paquete (▶ ida, ◀
  respuesta, ✕ perdido, ⏱ espera). Pruebas en
  `tests/test_tipos_paquete.py`. Tesis: párrafo nuevo en la sección de
  tipos de paquete (Cap. 5) y cita `Paxson2011RTO`.
- **Capturas con semilla fija.** `docs/guia_visual/capturar_tesis.py`
  rehace `fuerzas_cobertura.png` (`base`, semilla 2, 45 s) y
  `trafico.png` (`cobertura_edificio`, semilla 1, 50 s). Pies de figura
  al día con las cifras de esas corridas.
- **Punto 12, N1 sin ruta hacia N6 a los 40 s.** Es por el TTL de 6 de
  los OGM: con la semilla 1, N1 aprende la ruta a los 80.5 s; con TTL 7, a
  los 13 s. En 10 semillas con TTL 6, la primera ruta N1→N6 tarda 22.6 s
  en promedio, el 99.3 % de los pares tiene ruta a los 40 s y todos a los
  120 s. Con TTL 4 nunca aparece. Va en la tesis (descripción del OGM,
  Cap. 5) y en el caso 15 de `docs/guia_ejecucion.md`. No se cambia el
  TTL por defecto.
- **Punto 13, estadística.** `movilidad_datos`, `robustez` y
  `generalidad` pasaron de 10 a 30 semillas, y la tabla `diferencias`
  lleva el valor p de la prueba t pareada corregido por Holm
  (`analysis/capitulo5.py`, con pruebas en `tests/test_capitulo5.py`).
  Cambiaron cifras del Cap. 6, del resumen y de las conclusiones (fallos
  dirigidos: 0.338 frente a 0.542; edificio: 0.811 frente a 0.465). Lo
  más importante: en `colapso_progresivo`, la ventaja de la movilidad
  descentralizada sobre `repartir` deja de ser concluyente, así que **P7
  pasa a cumplirse en parte** (ahora son tres: P6, P7 y P9). Detalle en
  `OFICIAL.md` ("Resultados oficiales").
- **Arreglos de texto que dejó sugeridos Jefferson:**
  - Cap. 2: los emuladores no traen "listo para usar" un modelo de
    pérdida entre pisos.
  - Cap. 5: la frase "cada nodo conoce su posición" ya no se apoya en
    Howard et al.: queda como supuesto de este trabajo.
  - Cap. 6: Wang et al. (36.48 s de batman-adv para cambiar de Gateway)
    junto a la detección de caídas, aclarando que no se comparan de forma
    directa.
  - Conclusiones: la corrección por comparaciones múltiples cita a Holm
    (1979), no a Jain.

### Claude: pendiente

- **Punto 9, comparación cuantitativa con otro modelo.** Es la tarea más
  grande y la deuda principal de la tesis. Se hace en la máquina de Juan
  Camilo (Linux), porque ns-3 y batman-adv lo necesitan. Primero hay que
  fijar el alcance con Juan Camilo: qué herramienta (batman-adv real
  sobre interfaces de radio emuladas, que pide permisos de administrador,
  o ns-3, que no trae B.A.T.M.A.N. y obligaría a comparar con OLSR), qué
  escenario (el despliegue de referencia de 13 nodos) y qué métricas
  (entrega y tiempo de partición).

### Jefferson

En este orden:

1. **Su dedicatoria**, debajo de su nombre en
   `Plantilla/FrontMatter/F02-Dedication.tex`.
2. **Repetir en su máquina los tres lotes de 30 semillas** y comprobar que
   las tablas salen idénticas a las del repo (es la prueba P10, "idénticas
   en dos computadores"). `generalidad` tarda cerca de una hora:
   ```bash
   python main.py --batch lotes/movilidad_datos.json
   python main.py --batch lotes/robustez.json
   python main.py --batch lotes/generalidad.json
   python -m analysis.capitulo5
   git status Plantilla/MainMatter/Cap5/tablas   # no debe cambiar nada
   ```
   **Hecho el 2026-11-17** en la máquina de Jefferson (Windows, Python
   3.14): las diez tablas salieron idénticas a las del repo. En Windows
   tardaron 49 s, 16 s y 109 s. Las figuras de `Images/Cap5/` cambian de
   bytes solo porque matplotlib es otra versión (3.11.2 frente a 3.11.1);
   su contenido es el mismo y no se subieron. **P10 se cumple.**
3. **Punto 6, leer las fuentes completas** con la cuenta de la
   universidad, por orden de riesgo:
   1. Kiess y Mauve: la frase sobre la inundación en prototipos.
   2. Fontes et al.: "pares de interfaces virtuales" en Mininet-WiFi.
   3. Jain (1991): que respalde las diferencias pareadas por semilla
      (Cap. 4). La corrección por comparaciones múltiples ya no se le
      atribuye.
   4. Holm (1979): la referencia nueva del procedimiento de corrección.
   5. Zeng et al. (GloMoSim) y Riley y Henderson (ns-3).
   6. Howard et al.: ya no respalda la frase de la posición; sigue citado
      por la familia de las fuerzas virtuales. Basta comprobar eso.
4. **Punto 7, literatura reciente:** repetir la búsqueda en Scopus e IEEE
   Xplore (2022 a 2026: simulación de mallas, B.A.T.M.A.N., despliegue
   autónomo) y leer Farajkhah y Çoban (DOI 10.1016/j.simpat.2026.103372)
   antes de añadirlo.
5. **Punto 8, reescribir el estado del arte** (Cap. 3,
   `Plantilla/MainMatter/Cap2/M03-Chapter2.tex`) en lenguaje sencillo,
   después de 6 y 7. Regla de control: la lista de `\cite` debe ser la
   misma antes y después, salvo lo que añada el punto 7 (paso 4).
   **Primera versión hecha el 2026-11-17**, antes de los puntos 6 y 7:
   frases más cortas y una explicación breve de cada término técnico. Las
   51 fuentes y sus 68 citas, las etiquetas y las referencias cruzadas
   quedaron iguales, y lo que afirma cada párrafo no cambió. Falta que
   Jefferson la lea, y ajustarla si los puntos 6 y 7 cambian alguna frase.
6. **Punto 14, preparar la sustentación:** diapositivas y respuestas a:
   por qué no ns-3 (la propuesta aprobada en `VERIFICACION_FUENTES.md`),
   por qué no se validó con equipos, qué significa "código real" si no es
   batman-adv, por qué P6, P7 y P9 se cumplen solo en parte, y por qué el
   retardo de la pestaña Tráfico es una estimación y no una medición.
7. **Punto 2, lectura completa del PDF**, marcando lo que no se entienda
   sin saber de redes. Va al final, porque el punto 13 cambió cifras del
   Cap. 6, del resumen y de las conclusiones.

### Juan Camilo

- Su dedicatoria.
- Leer también el PDF completo (punto 2).
- Fijar con Claude el alcance del punto 9.

## Lo que queda fuera de los repartos

- Sigue sin leerse el texto completo de los artículos de pago: Jefferson
  no tuvo acceso desde su máquina (Springer, ScienceDirect, IEEE Xplore y
  ACM). Por eso el punto 6 va con la cuenta de la universidad.
