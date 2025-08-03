import streamlit as st
from pymongo import MongoClient
import openai
from PIL import Image
import io
import time
import pytz
from datetime import datetime

# === CONFIGURACIÓN APP ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CONEXIÓN SECRETS ===
MONGO_URI = st.secrets["mongo_uri"]
openai.api_key = st.secrets["openai_api_key"]

client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# === ZONA HORARIA COLOMBIA ===
tz = pytz.timezone("America/Bogota")

# === SUBIR IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if "objetos_detectados" not in st.session_state:
        st.session_state.objetos_detectados = []
        st.session_state.objetos_ordenados = []
        st.session_state.duraciones = []
        st.session_state.tiempo_inicio = None
        st.session_state.objeto_actual = None
        st.session_state.tiempo_total = 0
        st.session_state.modo_cronometro = False

    # === BOTÓN DE DETECCIÓN ===
    if st.button("🔎 Detectar objetos"):
        try:
            bytes_imagen = imagen.read()
            imagen_base64 = base64.b64encode(bytes_imagen).decode("utf-8")

            prompt = f"""Detecta solo los objetos físicos en esta imagen. Devuélveme solo una lista JSON de los nombres, sin explicaciones.
            Ejemplo: ["botella", "cuaderno", "maleta"]"""

            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis visual."},
                    {"role": "user", "content": f"La imagen está codificada en base64: {imagen_base64}\n{prompt}"}
                ],
                max_tokens=300,
                temperature=0.2
            )

            texto_respuesta = respuesta.choices[0].message.content.strip()
            objetos = eval(texto_respuesta)

            if isinstance(objetos, list) and objetos:
                st.session_state.objetos_detectados = objetos
                st.success("✅ Objetos detectados por IA.")
                st.rerun()
            else:
                st.warning("⚠️ No se detectaron objetos.")

        except Exception as e:
            st.error(f"Error en la detección: {e}")

# === SELECCIÓN DE OBJETOS PARA ORDENAR ===
if st.session_state.get("objetos_detectados"):
    st.markdown("### 📦 Objetos detectados:")
    seleccionados = []
    for obj in st.session_state.objetos_detectados:
        if st.checkbox(obj):
            seleccionados.append(obj)

    if seleccionados:
        st.session_state.objetos_ordenados = seleccionados
        st.session_state.duraciones = [0] * len(seleccionados)
        st.session_state.objeto_actual = 0
        st.session_state.tiempo_inicio = time.time()
        st.session_state.modo_cronometro = True
        st.success("🚀 Ordenamiento iniciado...")
        st.rerun()

# === CRONÓMETRO DE ORDENAMIENTO ===
if st.session_state.get("modo_cronometro"):
    objeto_actual = st.session_state.objeto_actual
    objetos = st.session_state.objetos_ordenados
    tiempo_inicio = st.session_state.tiempo_inicio

    if objeto_actual < len(objetos):
        transcurrido = int(time.time() - tiempo_inicio)
        st.markdown(f"🧱 Ordenando: **{objetos[objeto_actual]}**")
        st.markdown(f"⏱️ Tiempo actual: **{transcurrido} segundos**")

        if st.button("✅ Finalizar este objeto"):
            st.session_state.duraciones[objeto_actual] = transcurrido
            st.session_state.tiempo_total += transcurrido
            st.session_state.objeto_actual += 1
            if st.session_state.objeto_actual < len(objetos):
                st.session_state.tiempo_inicio = time.time()
            else:
                # === GUARDAR SESIÓN ===
                doc = {
                    "timestamp": datetime.now(tz),
                    "objetos": objetos,
                    "duraciones": st.session_state.duraciones,
                    "tiempo_total": st.session_state.tiempo_total
                }
                col.insert_one(doc)
                st.success("📦 Sesión registrada exitosamente en MongoDB.")
                st.balloons()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
            st.rerun()
    else:
        st.success("🎉 Todos los objetos fueron organizados.")
        st.session_state.modo_cronometro = False

# === HISTORIAL DE SESIONES ===
with st.expander("📚 Historial de sesiones"):
    try:
        historial = list(col.find({
            "objetos": {"$exists": True},
            "duraciones": {"$exists": True}
        }).sort("timestamp", -1))

        if historial:
            for idx, reg in enumerate(historial, start=1):
                fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
                st.markdown(f"### 📆 Sesión {idx} – {fecha}")

                objetos = reg["objetos"]
                duraciones = reg["duraciones"]
                total_segundos = reg["tiempo_total"]

                for i, obj in enumerate(objetos, start=1):
                    dur = duraciones[i - 1]
                    minutos = dur // 60
                    segundos = dur % 60
                    st.markdown(f"- {obj}: ⏱️ {minutos:02d}:{segundos:02d}")

                total_horas = total_segundos // 3600
                minutos_rest = (total_segundos % 3600) // 60
                segundos_rest = total_segundos % 60

                st.success(f"🧮 Tiempo total: {total_horas:02d}:{minutos_rest:02d}:{segundos_rest:02d}")
                st.divider()
        else:
            st.info("No hay sesiones completas registradas aún.")

    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")