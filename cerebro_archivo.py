import os
from datetime import datetime

def guardar_investigacion_local(rut, datos_ia):
    try:
        fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        ruta_carpeta = f"investigaciones/{rut}/{fecha_str}"
        if not os.path.exists(ruta_carpeta): os.makedirs(ruta_carpeta)
            
        with open(f"{ruta_carpeta}/informe.txt", "w", encoding="utf-8") as f:
            f.write(f"REPORTE VALENTIN SHIELD - RUT: {rut}\n\n")
            f.write(f"CAUSA RAÍZ: {datos_ia.get('causa_raiz')}\n")
            f.write("HECHOS:\n" + "\n".join(datos_ia.get('lista_hechos')))
            
        with open(f"{ruta_carpeta}/arbol.dot", "w", encoding="utf-8") as f:
            f.write(datos_ia.get('dot_code'))
            
        return ruta_carpeta
    except Exception as e:
        return f"Error: {e}"