"""Abrir la interfaz web en una ventana propia (Fase 3, parte 3).

Sin dependencias nuevas: en vez de pywebview (que en Linux necesita
compilar PyGObject y no se pudo instalar sin root), se usa el modo
aplicación de un navegador basado en Chromium (`--app=URL`), que abre la
interfaz en una ventana sin pestañas ni barra de direcciones. Si no hay
ninguno instalado, se abre el navegador por defecto, como siempre.
"""
import os
import shutil
import subprocess
import sys
import webbrowser

# Ejecutables con modo --app, en orden de preferencia.
NAVEGADORES_APP = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "brave-browser", "brave", "microsoft-edge", "microsoft-edge-stable",
    "vivaldi",
)

_RUTAS_MACOS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


def _rutas_windows():
    rutas = []
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                 os.environ.get("LOCALAPPDATA")):
        if base:
            rutas += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                      os.path.join(base, "BraveSoftware", "Brave-Browser",
                                   "Application", "brave.exe")]
    return rutas


def buscar_navegador_app(which=shutil.which, existe=os.path.isfile,
                         plataforma=sys.platform):
    """La ruta de un navegador con modo --app, o None si no hay ninguno."""
    for nombre in NAVEGADORES_APP:
        ruta = which(nombre)
        if ruta:
            return ruta
    if plataforma == "darwin":
        candidatas = _RUTAS_MACOS
    elif plataforma.startswith("win"):
        candidatas = _rutas_windows()
    else:
        candidatas = ()
    for ruta in candidatas:
        if existe(ruta):
            return ruta
    return None


def abrir_en_ventana(url, buscar=buscar_navegador_app, lanzar=subprocess.Popen,
                     abrir_navegador=webbrowser.open):
    """Abre `url` en una ventana propia si hay un navegador con modo --app;
    si no, en el navegador por defecto. Devuelve la ruta del navegador
    usado en modo app, o None si se usó el navegador por defecto."""
    navegador = buscar()
    if navegador:
        try:
            lanzar([navegador, f"--app={url}", "--new-window"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   start_new_session=True)
            return navegador
        except OSError:
            pass
    abrir_navegador(url)
    return None
