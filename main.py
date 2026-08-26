
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
    timeout=30.0,        # s sin señal de un compañero -> caído (regla pedida)
    beacon_cada=2.0,     # s entre beacons de identificación
    batman_cada=4.0,     # s entre OGMs propios (BATMAN)
    heartbeat_cada=8.0,  # s entre "estoy bien" de un rescatista
    ttl=6,   # saltos máximos de un OGM (del código real)
    battery_drain=0.030,      # % por segundo (rescatistas)
    battery_drain_surv=0.012, # % por segundo (celular de superviviente)
    rango_deteccion=7.0, # m: contacto físico con un superviviente
    move_speed=0.32,     # m por paso de un rescatista
)

# Colores
C_RESC   = ["#378ADD", "#1D9E75", "#9B59B6", "#E8A838",
            "#2E86C1", "#16A085", "#8E44AD", "#D4AC0D"]
C_SURV   = "#E24B4A"
C_SURV_OK = "#1D9E75"
C_DEAD   = "#8C8B85"
C_ALERT  = "#C0392B"
C_OGM    = "#F0A500"
C_BCN    = "#5DADE2"
C_HB     = "#27AE60"
C_HELP   = "#E74C3C"
C_MSG    = "#9B59B6"   # mensaje personalizado entre nodos (R o S)
C_BG     = "#F8F7F4"
C_WALL   = "#D3D1C7"
C_FLOOR  = "#E8E6E0"


def main():
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
        help="Ruta a un archivo JSON de escenario con nodos y posiciones "
             "explícitas (ver README). Tiene prioridad sobre --escenario "
             "y sobre -n/-g."
    )
    parser.add_argument(
        "--msg",
        type=str,
        default="Iniciando Red de Expansión de Cobertura...",
        help="Mensaje personalizado de inicio"
    )

    args = parser.parse_args()

    ancho, alto, piso_h, n_pisos = ANCHO, ALTO, PISO_H, N_PISOS
    stair_xy, stair_half_w = STAIR_XY, STAIR_HALF_W
    escenario_nombre = args.escenario

    config_path = args.config
    if config_path is None and args.escenario is not None:
        config_path = os.path.join(ESCENARIOS_DIR, f"{args.escenario}.json")

    if config_path:
        try:
            scenario = load_scenario(
                config_path,
                default_building=dict(ancho=ANCHO, alto=ALTO, piso_h=PISO_H,
                                       n_pisos=N_PISOS)
            )
        except ValueError as e:
            print(f"Error en archivo de escenario: {e}")
            sys.exit(1)

        building = scenario["building"]
        ancho = building.get("ancho", ANCHO)
        alto = building.get("alto", ALTO)
        piso_h = building.get("piso_h", PISO_H)
        n_pisos = building.get("n_pisos", N_PISOS)
        stair_xy = tuple(building.get("stair_xy", STAIR_XY))
        stair_half_w = building.get("stair_half_w", STAIR_HALF_W)
        escenario_nombre = scenario.get("name", config_path)

        n_total = len(scenario["nodes"])
        n_gw = sum(1 for n in scenario["nodes"] if n["role"] == "G")

        sim_config = dict(DEFAULTS)
        sim_config.update(scenario.get("medium", {}))
        sim_config.update(scenario.get("protocol", {}))
        sim_config["nodes"] = scenario["nodes"]
        sim_config["events"] = scenario.get("events", [])
        sim_config["n_nodes"] = n_total
        sim_config["n_gateways"] = n_gw

        print(f"\n{'='*60}")
        print(f" {args.msg}")
        print(f"{'='*60}")
        print(f" Configuración (desde {config_path}):")
        print(f"  - Nodos totales: {n_total}")
        print(f"  - Gateways:      {n_gw}")
        print(f"  - Escenario:     {escenario_nombre}")
        print(f"{'='*60}\n")
    else:
        if args.nodes <= 1:
            print("Error: El número de nodos debe ser mayor a 1 para simular una red ad-hoc.")
            sys.exit(1)

        if args.gateways >= args.nodes:
            print("Error: La cantidad de Gateways debe ser menor que el total de nodos.")
            sys.exit(1)

        escenario_nombre = "aleatorio"

        print(f"\n{'='*60}")
        print(f" {args.msg}")
        print(f"{'='*60}")
        print(f" Configuración:")
        print(f"  - Nodos totales: {args.nodes}")
        print(f"  - Gateways:      {args.gateways}")
        print(f"  - Escenario:     {escenario_nombre} (posiciones aleatorias)")
        print(f"{'='*60}\n")

        sim_config = {
            "n_nodes": args.nodes,
            "n_gateways": args.gateways,
            "rango_comm": 16.0,
            "timeout": 30.0,
            "battery_drain": 0.02,
        }

    try:
        # . Instanciar el motor de simulación

        sim = Simulation(escenario=escenario_nombre, cfg=sim_config,DEFAULTS=DEFAULTS,DT=DT,N_PISOS=n_pisos,PISO_H=piso_h,STAIR_XY=stair_xy,STAIR_HALF_W=stair_half_w,ANCHO=ancho,ALTO=alto,C_RESC=C_RESC,C_SURV=C_SURV,C_SURV_OK=C_SURV_OK,C_DEAD=C_DEAD,C_OGM=C_OGM,C_BCN=C_BCN,C_HB=C_HB)
        sim.C_BG = C_BG
        sim.C_WALL = C_WALL
        sim.C_FLOOR = C_FLOOR
        sim.C_ALERT = C_ALERT
        sim.C_MSG = C_MSG
        viz = Visualizer(sim)
        viz.run()

    except KeyboardInterrupt:
        print("\nSimulación finalizada por el usuario.")
    except Exception as e:
        print(f"\nError crítico en la simulación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()