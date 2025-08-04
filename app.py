import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIGURACIÓN DE LA APP ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA DE SECRETOS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
openai.api_key = OPENAI_API_KEY
tz = pytz.timezone("America/Bogota")

# === FUNCIONES ===
def convertir_imagen_base64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()

def reducir_imagen(imagen, max_ancho=600):
    if imagen.width > max_ancho:
        proporcion = max_ancho / imagen.width
        nuevo_tamano = (int(imagen.width * proporcion), int(imagen.height * proporcion))
        return imagen.resize(nuevo_tamano)
    return imagen

# === SESSION STATE ===
for key in ["seleccionados", "modo_zen", "tareas_zen", "indice_actual", "cronometro_inicio", "tiempos_zen", "mongo_id", "imagen_cargada", "nombre_archivo", "objetos_actuales"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "seleccionados" else []

if "file_uploader_key" not in st.session_state:
    st.session_state["file_uploader_key"] = "uploader_0"

# === RESUMEN TOTAL DE TIEMPOS ===
total_segundos = 0
for reg in col.find({"tiempos_zen": {"$exists": True}}):
    for entrada in reg["tiempos_zen"]:
        total_segundos += entrada.get("duracion_segundos", 0)

total_horas = total_segundos / 3600
progreso = min(total_horas / 10000, 1.0)

st.markdown(f"### ⏳ Progreso total: **{round(total_horas, 2)} / 10.000 horas**")
st.progress(progreso)

# === PESTAÑAS ===
tab_migracion, tab1, tab2, tab3 = st.tabs(["🧪 Migración", "🔍 Detección", "⏱️ Tiempo en vivo", "📚 Historial"])

# === TAB MIGRACIÓN ===
with tab_migracion:
    st.subheader("🧪 Captura con cámara (fluida y ligera)")

    # Inicializar estado
    claves = [
        "inicio_espera_foto", "foto_cargada", "imagen_b64", "imagen_para_mostrar",
        "tiempo_carga", "tiempo_analisis", "objetos_detectados", "orden_seleccionado",
        "modo_cronometro", "cronometro_inicio", "indice_actual_zen", "ubicaciones_zen"
    ]
    for clave in claves:
        if clave not in st.session_state:
            st.session_state[clave] = [] if "orden" in clave or "ubicaciones" in clave else None

    # MONGO para ubicación
    col_ubicaciones = db["registro_ubicaciones"]

    # PASO 1: Cargar imagen
    if not st.session_state["foto_cargada"]:
        st.session_state["inicio_espera_foto"] = time.time()
        archivo = st.file_uploader("📷 Toca para tomar foto (usa cámara móvil)", type=["jpg", "jpeg", "png"], label_visibility="collapsed", key="migracion_uploader_fluido")

        if archivo:
            tiempo_carga = round(time.time() - st.session_state["inicio_espera_foto"], 2)
            imagen = Image.open(archivo)
            imagen_reducida = reducir_imagen(imagen)
            imagen_b64 = convertir_imagen_base64(imagen_reducida)

            # GPT-4o directo
            with st.spinner("🔍 Analizando imagen..."):
                try:
                    inicio_analisis = time.time()
                    respuesta = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": "Detecta solo objetos visibles. Devuelve una lista clara, sin contexto extra."},
                                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + imagen_b64}}
                            ]}
                        ],
                        max_tokens=300
                    )
                    tiempo_analisis = round(time.time() - inicio_analisis, 2)
                    contenido = respuesta.choices[0].message.content
                    objetos = [obj.strip("-• ").capitalize() for obj in contenido.split("\n") if obj.strip()]

                    st.session_state.update({
                        "imagen_para_mostrar": imagen,
                        "imagen_b64": imagen_b64,
                        "tiempo_carga": tiempo_carga,
                        "tiempo_analisis": tiempo_analisis,
                        "objetos_detectados": objetos,
                        "foto_cargada": True,
                        "orden_seleccionado": [],
                        "indice_actual_zen": 0,
                        "modo_cronometro": False,
                        "ubicaciones_zen": []
                    })
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al analizar imagen: {e}")

    # PASO 2: Mostrar resultados y selección
    elif not st.session_state["modo_cronometro"]:
        with st.expander("📋 Sesión activa – Detalles de captura", expanded=True):
            st.image(st.session_state["imagen_para_mostrar"], caption="✅ Foto cargada", use_container_width=True)
            st.info(f"⏱ Tiempo hasta carga: {st.session_state['tiempo_carga']} s")
            st.success(f"🧠 Análisis GPT-4o: {st.session_state['tiempo_analisis']} s")

            st.markdown("### 🪄 Haz clic en los elementos en el orden que vas a trabajar:")

            for obj in st.session_state["objetos_detectados"]:
                if obj not in st.session_state["orden_seleccionado"]:
                    if st.button(obj, key=f"btn_{obj}"):
                        st.session_state["orden_seleccionado"].append(obj)
                        st.rerun()

            if st.session_state["orden_seleccionado"]:
                st.markdown("### ✅ Orden actual:")
                for i, item in enumerate(st.session_state["orden_seleccionado"], 1):
                    st.write(f"{i}. {item}")

                if len(st.session_state["orden_seleccionado"]) >= 1:
                    if st.button("✅ Confirmar orden y comenzar"):
                        st.session_state["modo_cronometro"] = True
                        st.session_state["cronometro_inicio"] = datetime.now(tz)
                        st.rerun()

    # PASO 3: Modo cronómetro
    elif st.session_state["modo_cronometro"]:
        tareas = st.session_state["orden_seleccionado"]
        idx = st.session_state["indice_actual_zen"]

        if idx < len(tareas):
            tarea_actual = tareas[idx]
            st.header(f"🧘 Tarea {idx + 1} de {len(tareas)}: {tarea_actual}")

            ahora = datetime.now(tz)
            inicio = st.session_state["cronometro_inicio"]
            transcurrido = str(ahora - inicio).split(".")[0]
            st.info(f"⏱ Tiempo transcurrido: {transcurrido}")

            if st.button("⏹️ Parar tarea"):
                st.session_state["duracion_actual"] = (ahora - inicio).total_seconds()
                st.session_state["cronometro_inicio"] = None
                st.session_state["esperando_ubicacion"] = True
                st.rerun()

        elif idx == len(tareas):
            st.success("🎉 Todas las tareas completadas.")
            if st.button("🔄 Nueva sesión"):
                for clave in claves:
                    st.session_state[clave] = [] if "orden" in clave or "ubicaciones" in clave else None
                st.rerun()

    # PASO 4: Ingresar ubicación después de parar
    if st.session_state.get("esperando_ubicacion"):
        ubicacion = st.text_input("📍 ¿Dónde quedó el elemento?", key="ubicacion_input")
        if st.button("📥 Guardar ubicación y continuar"):
            tarea = st.session_state["orden_seleccionado"][st.session_state["indice_actual_zen"]]
            col_ubicaciones.insert_one({
                "timestamp": datetime.now(tz),
                "elemento": tarea,
                "ubicacion": ubicacion,
                "duracion_segundos": st.session_state["duracion_actual"]
            })
            st.session_state["ubicaciones_zen"].append((tarea, ubicacion))
            st.session_state["indice_actual_zen"] += 1
            st.session_state["cronometro_inicio"] = datetime.now(tz)
            st.session_state["esperando_ubicacion"] = False
            st.rerun()

# === TAB 1: DETECCIÓN ===
with tab1:
    uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"], key=st.session_state["file_uploader_key"])
    if uploaded_file:
        imagen = Image.open(uploaded_file)
        st.image(imagen, caption="✅ Imagen cargada", use_container_width=True)
        st.session_state.imagen_cargada = imagen
        st.session_state.nombre_archivo = uploaded_file.name

        if st.button("🔍 Detectar objetos"):
            with st.spinner("Analizando imagen con GPT-4o..."):
                try:
                    b64_img = "data:image/jpeg;base64," + convertir_imagen_base64(imagen)
                    respuesta = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": "Detecta solo objetos u elementos visibles. Devuelve una lista clara y concisa de los objetos sin descripciones largas ni contexto adicional."},
                                {"type": "image_url", "image_url": {"url": b64_img}}
                            ]}
                        ],
                        max_tokens=300,
                    )
                    contenido = respuesta.choices[0].message.content
                    objetos = [obj.strip("-• ") for obj in contenido.split("\n") if obj.strip()]
                    st.session_state.seleccionados = []
                    st.session_state.objetos_actuales = objetos
                    st.session_state.modo_zen = False
                    st.session_state.tiempos_zen = []
                    st.session_state.mongo_id = None

                    if objetos:
                        st.success("✅ Objetos detectados:")
                        st.write(objetos)
                    else:
                        st.warning("⚠️ No se detectaron objetos en la imagen.")
                except Exception as e:
                    st.error(f"Error en la detección: {e}")

    if st.session_state.objetos_actuales:
        restantes = [obj for obj in st.session_state.objetos_actuales if obj not in st.session_state.seleccionados]
        st.markdown("**🖱️ Marca los elementos para la tarea monotarea:**")
        for obj in restantes:
            if st.checkbox(obj, key=f"chk_{obj}"):
                st.session_state.seleccionados.append(obj)
                st.rerun()

        if st.session_state.seleccionados:
            seleccionados_numerados = [f"{i+1}. {item}" for i, item in enumerate(st.session_state.seleccionados)]
            st.markdown("**📋 Orden de ejecución:**")
            st.multiselect("Seleccionados:", options=seleccionados_numerados, default=seleccionados_numerados, disabled=True)

        if st.button("🧘 Empezamos a ordenar"):
            if st.session_state["imagen_cargada"] is None:
                st.error("❌ No se encontró la imagen cargada.")
            else:
                with st.spinner("⏳ Guardando sesión y preparando modo zen..."):
                    imagen_reducida = reducir_imagen(st.session_state["imagen_cargada"])
                    imagen_b64 = convertir_imagen_base64(imagen_reducida)
                    doc = {
                        "timestamp": datetime.now(tz),
                        "objetos": st.session_state.objetos_actuales,
                        "nombre_archivo": st.session_state["nombre_archivo"],
                        "imagen_b64": imagen_b64
                    }
                    inserted = col.insert_one(doc)
                    st.session_state.mongo_id = inserted.inserted_id
                    st.session_state.tareas_zen = st.session_state.seleccionados.copy()
                    st.session_state.indice_actual = 0
                    st.session_state.modo_zen = True

                    # Restaurar pestaña 1 sin afectar pestaña 2
                    st.session_state.seleccionados = []
                    st.session_state.objetos_actuales = []
                    st.session_state.imagen_cargada = None
                    st.session_state.nombre_archivo = None
                    st.session_state["file_uploader_key"] = str(datetime.now().timestamp())

                    st.success("✅ Guardado. Ve a la pestaña **⏱️ Tiempo en vivo** para comenzar.")
                    time.sleep(1)
                    st.rerun()

# === TAB 2: TIEMPO EN VIVO ===
with tab2:
    if st.session_state.modo_zen and st.session_state.indice_actual is not None:
        tareas = st.session_state.tareas_zen
        idx = st.session_state.indice_actual

        if idx < len(tareas):
            tarea = tareas[idx]
            st.header(f"🧘 Tarea {idx + 1} de {len(tareas)}: {tarea}")

            if st.session_state.cronometro_inicio is None:
                if st.button("🎯 Empezar tarea"):
                    st.session_state.cronometro_inicio = datetime.now(tz)
                    st.rerun()
            else:
                cronometro_placeholder = st.empty()
                stop_button = st.button("✅ Tarea completada", key=f"done_{idx}")

                while True:
                    ahora = datetime.now(tz)
                    tiempo_transcurrido = ahora - st.session_state.cronometro_inicio
                    tiempo_str = str(tiempo_transcurrido).split(".")[0]
                    cronometro_placeholder.info(f"⏱ Tiempo: {tiempo_str}")
                    time.sleep(1)

                    if stop_button:
                        fin = datetime.now(tz)
                        st.session_state.tiempos_zen.append({
                            "nombre": tarea,
                            "tiempo_inicio": st.session_state.cronometro_inicio.isoformat(),
                            "tiempo_fin": fin.isoformat(),
                            "duracion_segundos": (fin - st.session_state.cronometro_inicio).total_seconds()
                        })
                        st.session_state.indice_actual += 1
                        st.session_state.cronometro_inicio = None
                        st.rerun()
                        break
        else:
            st.success("🎉 Modo zen completado. Tiempos registrados.")
            if st.session_state.mongo_id:
                col.update_one(
                    {"_id": st.session_state.mongo_id},
                    {"$set": {"tiempos_zen": st.session_state.tiempos_zen}}
                )
            else:
                st.warning("No se encontró ID de sesión para guardar los tiempos.")
    else:
        st.info("El modo zen no ha comenzado.")

# === TAB 3: HISTORIAL ===
with tab3:
    registros = list(col.find().sort("timestamp", -1))
    if registros:
        for reg in registros:
            fecha = reg.get("timestamp", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            with st.expander(f"🕓 {fecha}", expanded=False):
                if "imagen_b64" in reg:
                    st.image(Image.open(BytesIO(base64.b64decode(reg["imagen_b64"]))), width=300, caption="📸 Imagen registrada")

                st.write("📦 Objetos detectados:")
                for i, obj in enumerate(reg.get("objetos", []), 1):
                    st.write(f"- {obj}")

                # Mostrar métricas si existen
                if "tiempo_total_segundos" in reg or "tiempo_analisis_segundos" in reg or "tiempo_carga_segundos" in reg:
                    st.markdown("### ⏱️ Tiempos:")
                    if "tiempo_carga_segundos" in reg:
                        st.markdown(f"- 🕒 Carga: `{reg['tiempo_carga_segundos']} segundos`")
                    if "tiempo_analisis_segundos" in reg:
                        st.markdown(f"- 🧠 Análisis GPT-4o: `{reg['tiempo_analisis_segundos']} segundos`")
                    if "tiempo_total_segundos" in reg:
                        st.markdown(f"- 📥 Tiempo total desde carga: `{reg['tiempo_total_segundos']} segundos`")

                if "tiempos_zen" in reg:
                    st.markdown("⏱️ **Modo zen:**")
                    for i, t in enumerate(reg["tiempos_zen"], 1):
                        inicio = datetime.fromisoformat(t['tiempo_inicio']).astimezone(tz).strftime("%H:%M:%S")
                        fin = datetime.fromisoformat(t['tiempo_fin']).astimezone(tz).strftime("%H:%M:%S")
                        duracion = round(t['duracion_segundos'])
                        st.markdown(f"""
**{i}. {t['nombre']}**
- 🟢 Inicio: `{inicio}`
- 🔴 Fin: `{fin}`
- ⏱️ Duración: `{duracion} segundos`
                        """)
    else:
        st.info("No hay sesiones completas registradas aún.")