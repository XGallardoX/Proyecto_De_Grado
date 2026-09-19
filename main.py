
import argparse
import os
import sys

from sim.engine import Simulation
from sim.config_loader import load_scenario
from analysis.visualizer import Visualizer

ESCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escenarios")
ESCENARIOS_DISPONIBLES = ["base", "colapso_progresivo", "particion",
                          "rescatista_perdido", "denso"]

# Edificio
ANCHO  = 40.0
ALTO   = 30.0
PISO_H = 10.0
N_PISOS = 3
STAIR_XY = (20.0, 15.0)   # hueco de escalera (presente en todos los pisos)
STAIR_HALF_W = 1.7        # mitad del ancho del hueco de escalera (m)

# Tiempo de simulación
DT = 0.5  # segundos de tiempo simulado por paso

# Radio / medio 
DEFAULTS = dict(
    rango_comm=16.0,     # m: alcance máximo de radio
    perdida_base=0.02,   # prob. de pérdida incluso a 0 m
    falloff=0.85,        # cuánto degrada la fiabilidad con la distancia
    floor_atten=0.55,    # factor de atenuación extra por piso de diferencia
    timeout=30.0,        # s sin oír a otro gateway -> se lo marca caído
    beacon_cada=2.0,     # s entre beacons de identificación
    batman_cada=4.0,     # s entre OGMs propios (BATMAN)
    ttl=6,   # saltos máximos de un OGM (del código real)
    battery_drain=0.030,      # % por segundo (Gateways)
    battery_drain_nodo=0.012, # % por segundo (Nodos de usuario)
    move_speed=0.32,     # m por paso de un Gateway
)

# Colores
C_GATEWAY = ["#378ADD", "#1D9E75", "#9B59B6", "#E8A838",
             "#2E86C1", "#16A085", "#8E44AD", "#D4AC0D"]
C_NODO   = "#E24B4A"
C_DEAD   = "#8C8B85"
C_ALERT  = "#C0392B"
C_OGM    = "#F0A500"
C_BCN    = "#5DADE2"
C_MSG    = "#9B59B6"   # mensaje personalizado entre nodos (G o N)
C_BG     = "#F8F7F4"
C_WALL   = "#D3D1C7"
C_FLOOR  = "#E8E6E0"


def ruta_escenario(nombre):
    """Ruta del archivo de un escenario predefinido (--escenario)."""
    return os.path.join(ESCENARIOS_DIR, f"{nombre}.json")


def construir_simulacion(config_path=None, n_nodes=2, n_gateways=1,
                         static=False):
    """Arma una Simulation lista para correr.

    Con `config_path` carga el escenario (.json o .txt) con
    sim.config_loader; sin él, usa `n_nodes`/`n_gateways` con posiciones
    aleatorias. `static` fija los nodos (move_speed=0).

    Devuelve (sim, info), donde `info` resume la configuración para el
    banner de inicio. Lanza ValueError si el archivo de escenario o los
    parámetros son inválidos.
    """
    ancho, alto, piso_h, n_pisos = ANCHO, ALTO, PISO_H, N_PISOS
    stair_xy, stair_half_w = STAIR_XY, STAIR_HALF_W

    if config_path:
        scenario = load_scenario(
            config_path,
            default_building=dict(ancho=ANCHO, alto=ALTO, piso_h=PISO_H,
                                  n_pisos=N_PISOS)
        )

        building = scenario["building"]
        ancho = building.get("ancho", ANCHO)
        alto = building.get("alto", ALTO)
        piso_h = building.get("piso_h", PISO_H)
        n_pisos = building.get("n_pisos", N_PISOS)
        stair_xy = tuple(building.get("stair_xy", STAIR_XY))
        stair_half_w = building.get("stair_half_w", STAIR_HALF_W)
        escenario_nombre = scenario.get("name", config_path)

        sim_config = dict(DEFAULTS)
        sim_config.update(scenario.get("medium", {}))
        sim_config.update(scenario.get("protocol", {}))

        if "random" in scenario:
            n_total = scenario["random"]["n_nodes"]
            n_gw = scenario["random"]["n_gateways"]
            sim_config["n_nodes"] = n_total
            sim_config["n_gateways"] = n_gw
            posiciones = "aleatorias"
        else:
            n_total = len(scenario["nodes"])
            n_gw = sum(1 for n in scenario["nodes"] if n["role"] == "G")
            sim_config["nodes"] = scenario["nodes"]
            sim_config["events"] = scenario.get("events", [])
            sim_config["n_nodes"] = n_total
            sim_config["n_gateways"] = n_gw
            posiciones = "explícitas"
    else:
        if n_nodes <= 1:
            raise ValueError("El número de nodos debe ser mayor a 1 para "
                             "simular una red ad-hoc.")
        if n_gateways >= n_nodes:
            raise ValueError("La cantidad de Gateways debe ser menor que el "
                             "total de nodos.")

        escenario_nombre = "aleatorio"
        n_total, n_gw = n_nodes, n_gateways
        posiciones = "aleatorias"
        sim_config = {
            "n_nodes": n_nodes,
            "n_gateways": n_gateways,
            "rango_comm": 16.0,
            "timeout": 30.0,
            "battery_drain": 0.02,
        }

    if static:
        sim_config["move_speed"] = 0

    sim = Simulation(escenario=escenario_nombre, cfg=sim_config,DEFAULTS=DEFAULTS,DT=DT,N_PISOS=n_pisos,PISO_H=piso_h,STAIR_XY=stair_xy,STAIR_HALF_W=stair_half_w,ANCHO=ancho,ALTO=alto,C_GATEWAY=C_GATEWAY,C_NODO=C_NODO,C_DEAD=C_DEAD,C_OGM=C_OGM,C_BCN=C_BCN)
    sim.C_BG = C_BG
    sim.C_WALL = C_WALL
    sim.C_FLOOR = C_FLOOR
    sim.C_ALERT = C_ALERT
    sim.C_MSG = C_MSG

    info = dict(origen=config_path, escenario=escenario_nombre,
                n_total=n_total, n_gateways=n_gw, posiciones=posiciones)
    return sim, info


def imprimir_banner(msg, info):
    print(f"\n{'='*60}")
    print(f" {msg}")
    print(f"{'='*60}")
    if info["origen"]:
        print(f" Configuración (desde {info['origen']}):")
    else:
        print(" Configuración:")
    print(f"  - Nodos totales: {info['n_total']}")
    print(f"  - Gateways:      {info['n_gateways']}")
    print(f"  - Escenario:     {info['escenario']} (posiciones {info['posiciones']})")
    print(f"{'='*60}\n")


def crear_parser():
    parser = argparse.ArgumentParser(
        description="Simulador BATMAN - Red de Expansión de Cobertura",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # --- Parámetros de Configuración ---
    parser.add_argument(
        "-n", "--nodes",
        type=int,
        default=2,
        help="Cantidad total de nodos en la red (N > 1)"
    )
    parser.add_argument(
        "-g", "--gateways",
        type=int,
        default=1,
        help="Cantidad de nodos que actuarán como Gateway (conectados a Internet)"
    )
    parser.add_argument(
        "--escenario",
        type=str,
        default=None,
        choices=ESCENARIOS_DISPONIBLES,
        help="Escenario predefinido con nodos y posiciones fijas "
             f"(atajo a --config {ESCENARIOS_DIR}/<nombre>.json). "
             "Si no se pasa, usa -n/-g con posiciones aleatorias."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta a un archivo de escenario (.json o .txt, ver README) con "
             "nodos y posiciones explícitas, o en modo aleatorio. Tiene "
             "prioridad sobre --escenario y sobre -n/-g."
    )
    parser.add_argument(
        "--msg",
        type=str,
        default="Iniciando Red de Expansión de Cobertura...",
        help="Mensaje personalizado de inicio"
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Los nodos no se mueven: quedan fijos en su posición inicial "
             "(equivale a move_speed=0)."
    )
    return parser


def main(argv=None):
    args = crear_parser().parse_args(argv)

    config_path = args.config
    if config_path is None and args.escenario is not None:
        config_path = ruta_escenario(args.escenario)

    try:
        sim, info = construir_simulacion(config_path, args.nodes,
                                         args.gateways, args.static)
    except ValueError as e:
        if config_path:
            print(f"Error en archivo de escenario: {e}")
        else:
            print(f"Error: {e}")
        sys.exit(1)

    imprimir_banner(args.msg, info)

    def cargar_escenario(nombre):
        return construir_simulacion(ruta_escenario(nombre),
                                    static=args.static)[0]

    try:
        viz = Visualizer(sim, escenarios=ESCENARIOS_DISPONIBLES,
                         cargar_escenario=cargar_escenario)
        viz.run()

    except KeyboardInterrupt:
        print("\nSimulación finalizada por el usuario.")
    except Exception as e:
        print(f"\nError crítico en la simulación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
