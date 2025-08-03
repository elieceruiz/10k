import streamlit as st
from datetime import datetime, timedelta
import pytz
from pymongo import MongoClient
import openai
from PIL import Image
import io
import base64
import re

# === CONFIG STREAMLIT ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CONEXIÓN A MONGODB ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- CLAVE OPENAI ---
openai.api_key = st.secrets["openai_api_key"]

# --- ZONA HORARIA CO ---
tz = pytz.timezone("America/Bogota")

# === FUNCIÓN IA PARA DETECCIÓN ===
def analizar_imagen_con_openai(image_bytes):
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    respuesta = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "Detecta objetos presentes en esta imagen. Devuelve una lista JSON con los nombres de los objetos detectados, sin explicaciones."},
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}],
            },
        ],
        temperature=0,
        max_tokens=150,
    )
    return respuesta.choices[0].message.content.strip()

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)
    image_bytes = imagen.read()

    if "objetos_detectados" not in st.session_state:
        try:
            texto = analizar_imagen_con_openai(image_bytes)
            match = re.search(r"\[.*?\]", texto, re.DOTALL)
            if match:
                objetos = eval(match.group(0))
                if isinstance(objetos, list):
                    st.session_state.objetos_detectados = objetos
                    st.success("✅ Objetos detectados correctamente.")
                else:
                    st.warning("⚠️ La respuesta no es una lista válida.")
            else:
                st.warning("⚠️ No se detectó una lista en la respuesta.")
        except Exception as e:
            st.error(f"❌ Error al procesar imagen: {e}")

# === PASO 2: SELECCIÓN Y ORDENAMIENTO ===
if "objetos_detectados" in st.session_state:
    st.subheader("🧩 Selecciona el objeto a ordenar:")

    if "registro_objetos" not in st.session_state:
        st.session_state.registro_objetos = []

    objeto_actual = st.selectbox("🔽 Objeto", st.session_state.objetos_detectados)

    if st.button("🟢 Iniciar ordenamiento de este objeto"):
        st.session_state.objeto_en_proceso = objeto_actual
        st.session_state.tiempo_inicio = datetime.now(tz)

# === PASO 3: CRONÓMETRO INDIVIDUAL ===
if "objeto_en_proceso" in st.session_state and "tiempo_inicio" in st.session_state:
    st.markdown(f"### ⏱ Ordenando: `{st.session_state.objeto_en_proceso}`")

    tiempo_actual = datetime.now(tz)
    tiempo_transcurrido = tiempo_actual - st.session_state.tiempo_inicio
    segundos = int(tiempo_transcurrido.total_seconds())
    minutos = segundos // 60
    st.info(f"🧭 Tiempo transcurrido: {minutos:02d}:{segundos%60:02d}")

    if st.button("✅ Finalizar y guardar este objeto"):
        doc = {
            "objeto": st.session_state.objeto_en_proceso,
            "duracion_segundos": segundos,
            "timestamp": datetime.now(tz),
        }
        col.insert_one(doc)
        st.success(f"✅ `{st.session_state.objeto_en_proceso}` guardado correctamente.")
        st.session_state.objetos_detectados.remove(st.session_state.objeto_en_proceso)
        del st.session_state.objeto_en_proceso
        del st.session_state.tiempo_inicio

# === PASO 4: AVANCE GLOBAL ===
registros = list(col.find({}))
total_segundos = sum(r.get("duracion_segundos", 0) for r in registros)
total_horas = total_segundos / 3600

st.markdown("---")
st.markdown(f"📊 **Horas acumuladas hacia las 10.000:** `{total_horas:.2f}`")
st.markdown("🔗 [Ver saldo y uso de OpenAI](https://platform.openai.com/usage)")