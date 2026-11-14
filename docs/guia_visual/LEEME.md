# Fuente de la guía visual

`docs/guia_visual_simulador.pdf` sale de `guia.html` y de capturas de la
interfaz web. Esta carpeta guarda la fuente y los guiones para rehacerla
cuando cambie la interfaz. Las capturas y las tipografías no se guardan:
se generan o se descargan.

## Cómo regenerar el PDF

Hace falta Google Chrome, Pillow (viene con matplotlib) y Playwright
(`pip install playwright`; no hay que descargar su navegador). Desde la
raíz del repo:

```bash
# 1. El servidor, en otra terminal
python main.py --web --config escenarios/fallos/fallo_puente.txt --seed 1 --trafico 6 --puerto 8771 --no-abrir

# 2. Las capturas (PNG) y su paso a JPG
mkdir -p tmp_guia/capturas
python docs/guia_visual/capturar1.py tmp_guia/capturas
python docs/guia_visual/capturar2.py tmp_guia/capturas
python docs/guia_visual/a_jpg.py tmp_guia/capturas docs/guia_visual/img

# 3. El PDF
python docs/guia_visual/a_pdf.py docs/guia_visual/guia.html docs/guia_visual_simulador.pdf
```

- `capturar1.py` usa `fallo_puente` y se detiene en los 55, 123 y 206 s,
  que son los instantes que cita el texto. Al final manda 10 ecos de ICMP
  y 10 segmentos de TCP de N1 a N6 para la página de la pestaña Tráfico.
- `capturar2.py` carga `campo_abierto` y `base`, y corre
  `lotes/robustez.json` en el laboratorio.
- `guia.html` espera `inter.woff2` y `jetbrains-mono.woff2` a su lado
  (Inter y JetBrains Mono). Sin ellas el PDF sale con la tipografía por
  defecto.
- Si una captura cambia, hay que revisar las cifras que el texto cita de
  ella: la matriz (154 de 156), la tasa de entrega (59.8 %), las edades
  de las rutas a los 123 s, el tiempo del laboratorio y la nota de la
  página de Tráfico.

`docs/guia_visual/img/` y `tmp_guia/` no se suben al repo.

## Capturas de la tesis

`capturar_tesis.py` rehace con semilla fija dos capturas del Capítulo 5
de la tesis (`Plantilla/Images/Cap4/`): `fuerzas_cobertura.png`
(`base`, semilla 2, 45 s) y `trafico.png` (`cobertura_edificio`,
semilla 1, 50 s). Con el mismo servidor de arriba:

```bash
python docs/guia_visual/capturar_tesis.py tmp_guia/tesis
cp tmp_guia/tesis/*.png Plantilla/Images/Cap4/
```

Avanza paso a paso, así que la imagen sale igual en cualquier máquina.
Imprime las cifras del panel Tráfico que cita el pie de figura.
