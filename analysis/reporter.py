import csv
import json
import os
import time
from collections import defaultdict

def export_simulation_reports(sim):
    """
    Exports simulation results to CSV, JSON, and TEXT files in Spanish.
    """
    ts = time.strftime('%Y%m%d_%H%M%S')
    escenario = getattr(sim, "escenario", "desconocido")
    
    csv_fn = f"reporte_{escenario}_{ts}.csv"
    json_fn = f"reporte_{escenario}_{ts}.json"
    text_fn = f"reporte_{escenario}_{ts}.txt"
    
    rec = getattr(sim, "recorder", None)
    if not rec or not hasattr(rec, "t") or len(rec.t) == 0:
        print("[reporter] Advertencia: No hay datos registrados en la simulación.")
        return {}

    t_len = len(rec.t)
    
    events_by_time = defaultdict(list)
    for t_evt, tipo, txt in rec.events:
        events_by_time[round(t_evt, 3)].append((tipo, txt))
    
    # -------------------------------
    # 1. GENERAR REPORTE CSV
    # -------------------------------
    try:
        headers = [
            "tiempo_s",
            "gateways_o_rescatistas_activos",
            "nodos_o_supervivientes_activos",
            "componentes_de_malla",
            "nodos_o_supervivientes_alcanzables",
            "calidad_ruta_promedio_tq",
            "saltos_promedio",
            "silencio_maximo_s",
            "tasa_entrega_paquetes",
            "alertas_activas",
            "ancho_banda_total_mbps",
            "supervivientes_hallados_acumulado",
            "tipo_evento",
            "descripcion_evento"
        ]
        
        with open(csv_fn, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for i in range(t_len):
                t_val = rec.t[i]
                
                # Extraer valores adaptativos con hasattr
                alive_1 = rec.alive_G[i] if hasattr(rec, 'alive_G') and i < len(rec.alive_G) else (
                    rec.alive_R[i] if hasattr(rec, 'alive_R') and i < len(rec.alive_R) else 0
                )
                alive_2 = rec.alive_N[i] if hasattr(rec, 'alive_N') and i < len(rec.alive_N) else (
                    rec.alive_S[i] if hasattr(rec, 'alive_S') and i < len(rec.alive_S) else 0
                )
                comp = rec.comp_G[i] if hasattr(rec, 'comp_G') and i < len(rec.comp_G) else (
                    rec.comp_R[i] if hasattr(rec, 'comp_R') and i < len(rec.comp_R) else 0
                )
                reach = rec.node_reach[i] if hasattr(rec, 'node_reach') and i < len(rec.node_reach) else (
                    rec.surv_reach[i] if hasattr(rec, 'surv_reach') and i < len(rec.surv_reach) else 0
                )
                
                avg_tq = rec.avg_tq[i] if hasattr(rec, 'avg_tq') and i < len(rec.avg_tq) else 0.0
                avg_hops = rec.avg_hops[i] if hasattr(rec, 'avg_hops') and i < len(rec.avg_hops) else 0.0
                max_silence = rec.max_silence[i] if hasattr(rec, 'max_silence') and i < len(rec.max_silence) else 0.0
                deliver_ratio = rec.deliver_ratio[i] if hasattr(rec, 'deliver_ratio') and i < len(rec.deliver_ratio) else 1.0
                alerts_active = rec.alerts_active[i] if hasattr(rec, 'alerts_active') and i < len(rec.alerts_active) else 0
                bandwidth = rec.bandwidth[i] if hasattr(rec, 'bandwidth') and i < len(rec.bandwidth) else 0.0
                found_cum = rec.found_cum[i] if hasattr(rec, 'found_cum') and i < len(rec.found_cum) else (
                    len(sim.found_ids) if hasattr(sim, 'found_ids') else 0
                )
                
                evts = events_by_time.get(round(t_val, 3), [])
                if evts:
                    event_type = " | ".join(e[0] for e in evts)
                    event_desc = " | ".join(e[1] for e in evts)
                else:
                    event_type = ""
                    event_desc = ""
                
                writer.writerow([
                    t_val,
                    alive_1,
                    alive_2,
                    comp,
                    reach,
                    avg_tq,
                    avg_hops,
                    max_silence,
                    deliver_ratio,
                    alerts_active,
                    bandwidth,
                    found_cum,
                    event_type,
                    event_desc
                ])
                
        print(f"[reporter] Reporte exportado a CSV: {csv_fn}")
    except Exception as e:
        print(f"[reporter] Error exportando CSV: {e}")

    # -------------------------------
    # 2. GENERAR REPORTE JSON
    # -------------------------------
    try:
        node_roles = {}
        for n in sim.nodes.values():
            role = n.role
            if role not in node_roles:
                node_roles[role] = {"total": 0, "activos": 0}
            node_roles[role]["total"] += 1
            if n.alive:
                node_roles[role]["activos"] += 1
                
        summary_data = {
            "tiempo_final_s": sim.t,
            "nodos_por_rol": node_roles,
            "componentes_finales": getattr(sim, "_prev_components", 1),
            "total_eventos": len(rec.events),
            "paquetes_transmitidos": getattr(sim.medium, "attempted", 0),
            "paquetes_recibidos": getattr(sim.medium, "delivered", 0),
        }
        
        if summary_data["paquetes_transmitidos"] > 0:
            summary_data["tasa_entrega_paquetes"] = summary_data["paquetes_recibidos"] / summary_data["paquetes_transmitidos"]
        else:
            summary_data["tasa_entrega_paquetes"] = 1.0
            
        if hasattr(sim, "found_ids"):
            summary_data["supervivientes_hallados"] = len(sim.found_ids)
            
        surv_nodes = [n for n in sim.nodes.values() if n.role == 'S']
        if surv_nodes:
            summary_data["total_supervivientes"] = len(surv_nodes)

        metrics_list = []
        for i in range(t_len):
            alive_1 = rec.alive_G[i] if hasattr(rec, 'alive_G') and i < len(rec.alive_G) else (
                rec.alive_R[i] if hasattr(rec, 'alive_R') and i < len(rec.alive_R) else 0
            )
            alive_2 = rec.alive_N[i] if hasattr(rec, 'alive_N') and i < len(rec.alive_N) else (
                rec.alive_S[i] if hasattr(rec, 'alive_S') and i < len(rec.alive_S) else 0
            )
            comp = rec.comp_G[i] if hasattr(rec, 'comp_G') and i < len(rec.comp_G) else (
                rec.comp_R[i] if hasattr(rec, 'comp_R') and i < len(rec.comp_R) else 0
            )
            reach = rec.node_reach[i] if hasattr(rec, 'node_reach') and i < len(rec.node_reach) else (
                rec.surv_reach[i] if hasattr(rec, 'surv_reach') and i < len(rec.surv_reach) else 0
            )
            avg_tq = rec.avg_tq[i] if hasattr(rec, 'avg_tq') and i < len(rec.avg_tq) else 0.0
            avg_hops = rec.avg_hops[i] if hasattr(rec, 'avg_hops') and i < len(rec.avg_hops) else 0.0
            max_silence = rec.max_silence[i] if hasattr(rec, 'max_silence') and i < len(rec.max_silence) else 0.0
            deliver_ratio = rec.deliver_ratio[i] if hasattr(rec, 'deliver_ratio') and i < len(rec.deliver_ratio) else 1.0
            alerts_active = rec.alerts_active[i] if hasattr(rec, 'alerts_active') and i < len(rec.alerts_active) else 0
            bandwidth = rec.bandwidth[i] if hasattr(rec, 'bandwidth') and i < len(rec.bandwidth) else 0.0
            found_cum = rec.found_cum[i] if hasattr(rec, 'found_cum') and i < len(rec.found_cum) else (
                len(sim.found_ids) if hasattr(sim, 'found_ids') else 0
            )

            metrics_list.append({
                "tiempo_s": rec.t[i],
                "gateways_o_rescatistas_activos": alive_1,
                "nodos_o_supervivientes_activos": alive_2,
                "componentes_malla": comp,
                "nodos_o_supervivientes_alcanzables": reach,
                "calidad_ruta_promedio_tq": avg_tq,
                "saltos_promedio": avg_hops,
                "silencio_maximo_s": max_silence,
                "tasa_entrega_paquetes": deliver_ratio,
                "alertas_activas": alerts_active,
                "ancho_banda_total_mbps": bandwidth,
                "supervivientes_hallados_acumulado": found_cum
            })

        events_list = []
        for t_evt, tipo, txt in rec.events:
            events_list.append({
                "tiempo_s": t_evt,
                "tipo_evento": tipo,
                "descripcion": txt
            })

        json_data = {
            "metadatos": {
                "escenario": escenario,
                "fecha_ejecucion": time.strftime('%Y-%m-%d %H:%M:%S'),
                "configuracion": {k: v for k, v in sim.cfg.items() if isinstance(v, (int, float, str, bool, list))}
            },
            "resumen": summary_data,
            "serie_temporal_metricas": metrics_list,
            "eventos": events_list
        }
        
        with open(json_fn, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"[reporter] Reporte exportado a JSON: {json_fn}")
    except Exception as e:
        print(f"[reporter] Error exportando JSON: {e}")

    # -----------------------------
    # 3. GENERAR REPORTE TEXTO
    # -----------------------------
    try:
        with open(text_fn, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("             REPORTE DE SIMULACIÓN AD-HOC BATMAN\n")
            f.write("=" * 60 + "\n")
            f.write(f"Fecha de Ejecución : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Escenario          : {escenario.upper()}\n")
            f.write(f"Tiempo Simulado    : {sim.t:.1f} s\n")
            f.write("-" * 60 + "\n")
            
            f.write("PARÁMETROS DE CONFIGURACIÓN DE LA RED:\n")
            cfg_dict = {k: v for k, v in sim.cfg.items() if isinstance(v, (int, float, str, bool))}
            for k, v in sorted(cfg_dict.items()):
                f.write(f"  - {k:<25}: {v}\n")
            f.write("-" * 60 + "\n")
            
            f.write("ESTADÍSTICAS FINALES:\n")
            for role, counts in node_roles.items():
                role_name = f"Rol '{role}'"
                if role == 'G':
                    role_name = "Gateway (G)"
                elif role == 'N':
                    role_name = "Nodo de Usuario (N)"
                elif role == 'R':
                    role_name = "Rescatista (R)"
                elif role == 'S':
                    role_name = "Superviviente (S)"
                f.write(f"  - Nodos {role_name:<23}: {counts['activos']} activos / {counts['total']} totales\n")
                
            f.write(f"  - Componentes de Red (Malla)  : {summary_data['componentes_finales']}\n")
            f.write(f"  - Cantidad de Eventos         : {summary_data['total_eventos']}\n")
            f.write(f"  - Paquetes Radio Transmitidos : {summary_data['paquetes_transmitidos']}\n")
            f.write(f"  - Paquetes Radio Recibidos    : {summary_data['paquetes_recibidos']}\n")
            pct = summary_data['tasa_entrega_paquetes'] * 100
            f.write(f"  - Eficiencia del Canal Radio  : {pct:.2f}%\n")
            
            if "supervivientes_hallados" in summary_data:
                f.write(f"  - Supervivientes Encontrados  : {summary_data['supervivientes_hallados']} / {summary_data.get('total_supervivientes', 0)}\n")
            f.write("-" * 60 + "\n")
            
            if len(rec.t) > 0:
                f.write("PROMEDIOS DE RENDIMIENTO:\n")
                avg_tq_val = sum(rec.avg_tq) / len(rec.avg_tq) if hasattr(rec, 'avg_tq') and rec.avg_tq else 0.0
                avg_hops_val = sum(rec.avg_hops) / len(rec.avg_hops) if hasattr(rec, 'avg_hops') and rec.avg_hops else 0.0
                
                bw_list = rec.bandwidth if hasattr(rec, 'bandwidth') and rec.bandwidth else []
                avg_bw_val = sum(bw_list) / len(bw_list) if bw_list else 0.0
                
                f.write(f"  - Calidad de Ruta Promedio (TQ): {avg_tq_val:.4f}\n")
                f.write(f"  - Saltos Promedio en Rutas    : {avg_hops_val:.2f}\n")
                if avg_bw_val > 0:
                    f.write(f"  - Ancho de Banda Red Promedio : {avg_bw_val:.2f} Mbps\n")
                f.write("-" * 60 + "\n")
            
            f.write("CRONOLOGÍA DE EVENTOS REGISTRADOS:\n")
            if rec.events:
                for t_evt, tipo, txt in rec.events:
                    f.write(f"  [{t_evt:6.1f}s] {tipo:<12} {txt}\n")
            else:
                f.write("  (No se registraron eventos durante esta simulación)\n")
            f.write("=" * 60 + "\n")
            
        print(f"[reporter] Reporte exportado a TEXTO: {text_fn}")
    except Exception as e:
        print(f"[reporter] Error exportando reporte de texto: {e}")

    return {
        "csv": csv_fn,
        "json": json_fn,
        "text": text_fn
    }
