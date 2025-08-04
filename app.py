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

# === PESTAÑA: ORDEN Y UBICACIÓN DE ELEMENTOS DETECTADOS ===
with tab_migracion:
    st.subheader("📸 Captura y ubicación de elementos")

    # === Sesión inicial ===
    if "flujo_etapa" not in st.session_state:
        st.session_state["flujo_etapa"] = "esperando_foto"
        st.session_state["elementos_detectados"] = []
        st.session_state["orden_seleccionado"] = []
        st.session_state["elemento_actual"] = None
        st.session_state["inicio_cronometro"] = None
        st.session_state["duraciones"] = []
        st.session_state["ubicaciones"] = []
        st.session_state["index"] = 0

    # === Etapa 1: Captura ===
    if st.session_state["flujo_etapa"] == "esperando_foto":
        st.info("📷 Toma o sube una foto para iniciar.")
        archivo = st.file_uploader("Capturar imagen", type=["jpg", "jpeg", "png"], key="uploader_ubicacion")

        if archivo:
            with st.spinner("📷 Cargando imagen..."):
                img = Image.open(archivo)
                b64_img = convertir_imagen_base64(img)
                st.session_state["imagen_base64"] = "data:image/jpeg;base64," + b64_img
                st.image(img, caption="✅ Imagen cargada", use_container_width=True)
                st.session_state["flujo_etapa"] = "analizando"
                st.rerun()

    # === Etapa 2: Análisis GPT-4o ===
    elif st.session_state["flujo_etapa"] == "analizando":
        with st.spinner("🤖 Analizando imagen con GPT-4o..."):
            try:
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "Detecta objetos visibles y devuélvelos como lista JSON simple, sin contexto."},
                            {"type": "image_url", "image_url": {"url": st.session_state["imagen_base64"]}}
                        ]}
                    ],
                    max_tokens=300
                )
                texto = respuesta.choices[0].message.content
                objetos = [o.strip("-• ").capitalize() for o in texto.split("\n") if o.strip()]
                st.session_state["elementos_detectados"] = objetos
                st.session_state["flujo_etapa"] = "ordenar"
                st.success(f"✅ {len(objetos)} elementos detectados")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al analizar: {e}")

    # === Etapa 3: Selección ordenada ===
    elif st.session_state["flujo_etapa"] == "ordenar":
        st.markdown("### 🧠 Seleccioná los elementos en el orden que vas a ubicarlos")
        seleccionados = st.session_state["orden_seleccionado"]
        opciones = [e for e in st.session_state["elementos_detectados"] if e not in seleccionados]

        cols = st.columns(3)
        for i, e in enumerate(opciones):
            if cols[i % 3].button(e):
                st.session_state["orden_seleccionado"].append(e)
                st.rerun()

        if seleccionados:
            st.markdown("#### ✅ Orden actual:")
            st.write(" → ".join(seleccionados))

        if seleccionados:
            if st.button("✅ Confirmar orden"):
                st.session_state["flujo_etapa"] = "ejecucion"
                st.session_state["elemento_actual"] = seleccionados[0]
                st.session_state["inicio_cronometro"] = time.time()
                st.rerun()

    # === Etapa 4: Ejecución secuencial ===
    elif st.session_state["flujo_etapa"] == "ejecucion":
        actual = st.session_state["elemento_actual"]
        st.markdown(f"### 🟢 Ubicando: `{actual}`")
        cronometro = st.empty()
        duracion = int(time.time() - st.session_state["inicio_cronometro"])
        cronometro.markdown(f"🕒 Tiempo: `{timedelta(seconds=duracion)}`")

        if st.button("⏹ Finalizar y registrar ubicación"):
            st.session_state["duraciones"].append(duracion)
            st.session_state["flujo_etapa"] = "ubicacion"
            st.rerun()

    # === Etapa 5: Ubicar el elemento ===
    elif st.session_state["flujo_etapa"] == "ubicacion":
        actual = st.session_state["elemento_actual"]
        ubicacion = st.text_input(f"¿Dónde quedó ubicado '{actual}'?", key=f"ubicacion_{actual}")

        if st.button("💾 Guardar ubicación"):
            st.session_state["ubicaciones"].append(ubicacion)
            st.session_state["index"] += 1

            if st.session_state["index"] < len(st.session_state["orden_seleccionado"]):
                nuevo = st.session_state["orden_seleccionado"][st.session_state["index"]]
                st.session_state["elemento_actual"] = nuevo
                st.session_state["inicio_cronometro"] = time.time()
                st.session_state["flujo_etapa"] = "ejecucion"
                st.rerun()
            else:
                st.session_state["flujo_etapa"] = "resumen"
                st.rerun()

    # === Etapa final: Resumen y guardar ===
    elif st.session_state["flujo_etapa"] == "resumen":
        st.success("✅ Ubicación completada")
        resumen = pd.DataFrame({
            "Elemento": st.session_state["orden_seleccionado"],
            "Ubicación": st.session_state["ubicaciones"],
            "Duración": [str(timedelta(seconds=d)) for d in st.session_state["duraciones"]]
        })
        st.dataframe(resumen, use_container_width=True)

        if st.button("📦 Guardar todo en base de datos"):
            for i in range(len(st.session_state["orden_seleccionado"])):
                col.insert_one({
                    "elemento": st.session_state["orden_seleccionado"][i],
                    "ubicacion": st.session_state["ubicaciones"][i],
                    "duracion": st.session_state["duraciones"][i],
                    "timestamp": datetime.now(tz)
                })
            st.success("✅ Todo registrado")

            # Reiniciar todo
            for key in ["flujo_etapa", "elementos_detectados", "orden_seleccionado", "elemento_actual", "inicio_cronometro", "duraciones", "ubicaciones", "index", "imagen_base64"]:
                st.session_state.pop(key, None)
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