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

# === CONFIGURACIÓN DE CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = OPENAI_API_KEY
tz = pytz.timezone("America/Bogota")

# === FUNCIÓN PARA CONVERTIR IMAGEN A BASE64 ===
def convertir_imagen_base64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_b64}"

# === SESSION STATE ===
for key in ["seleccionados", "modo_zen", "tareas_zen", "indice_actual", "cronometro_inicio", "tiempos_zen", "mongo_id"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "seleccionados" else []

# === SUBIDA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    imagen = Image.open(uploaded_file)
    st.image(imagen, caption="✅ Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        with st.spinner("Analizando imagen con GPT-4o..."):
            try:
                b64_img = convertir_imagen_base64(imagen)
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

# === MODO ZEN ===
if st.session_state.modo_zen:
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
            cronometro_area = st.empty()
            boton_area = st.empty()

            while True:
                tiempo_transcurrido = datetime.now(tz) - st.session_state.cronometro_inicio
                tiempo_str = str(tiempo_transcurrido).split(".")[0]
                cronometro_area.info(f"⏱ Tiempo: {tiempo_str}")

                if boton_area.button("✅ Tarea completada"):
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

                time.sleep(1)
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
    if "objetos_actuales" in st.session_state:
        restantes = [obj for obj in st.session_state.objetos_actuales if obj not in st.session_state.seleccionados]
        st.markdown("**🖱️ Marca los elementos para la tarea monotarea:**")
        for i, obj in enumerate(restantes):
            if st.checkbox(obj, key=f"chk_{obj}"):
                st.session_state.seleccionados.append(obj)
                st.rerun()

        if st.session_state.seleccionados:
            seleccionados_numerados = [f"{i+1}. {item}" for i, item in enumerate(st.session_state.seleccionados)]
            st.markdown("**📋 Orden de ejecución:**")
            st.multiselect("Seleccionados:", options=seleccionados_numerados, default=seleccionados_numerados, disabled=True)

        if st.button("🧘 Empezamos a ordenar"):
            doc = {
                "timestamp": datetime.now(tz),
                "objetos": st.session_state.objetos_actuales,
                "nombre_archivo": uploaded_file.name
            }
            inserted = col.insert_one(doc)
            st.session_state.mongo_id = inserted.inserted_id
            st.session_state.tareas_zen = st.session_state.seleccionados.copy()
            st.session_state.indice_actual = 0
            st.session_state.modo_zen = True
            st.rerun()

# === HISTORIAL DE SESIONES ===
st.subheader("📚 Historial de sesiones")
registros = list(col.find().sort("timestamp", -1))
if registros:
    for reg in registros:
        fecha = reg.get("timestamp", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🕓 {fecha}**")
        st.write("📦 Objetos detectados:")
        for i, obj in enumerate(reg.get("objetos", []), 1):
            st.write(f"- {obj}")
        if "tiempos_zen" in reg:
            st.markdown("⏱️ **Modo zen:**")
            for i, t in enumerate(reg["tiempos_zen"], 1):
                st.write(f"{i}. {t['nombre']} – {round(t['duracion_segundos'])}s")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")
