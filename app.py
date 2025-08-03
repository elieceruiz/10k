import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import pytz
import io
import openai
import base64
import time

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETS Y CONFIGURACIÓN ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === ESTADO DE SESIÓN ===
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []

if "objetos_seleccionados" not in st.session_state:
    st.session_state.objetos_seleccionados = []

if "cronometro_activo" not in st.session_state:
    st.session_state.cronometro_activo = False

if "inicio_sesion" not in st.session_state:
    st.session_state.inicio_sesion = None

# === FUNCIÓN PARA DETECTAR OBJETOS ===
def detectar_objetos_con_openai(imagen):
    try:
        imagen_bytes = io.BytesIO()
        imagen.save(imagen_bytes, format="JPEG")
        imagen_bytes = imagen_bytes.getvalue()
        imagen_base64 = base64.b64encode(imagen_bytes).decode("utf-8")

        prompt = (
            "Lista los objetos principales visibles en esta imagen. "
            "Sé breve, responde solo con una lista de objetos detectados."
        )

        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente de visión computacional."},
                {"role": "user", "content": f"La siguiente imagen es base64: {imagen_base64} {prompt}"}
            ],
            max_tokens=300,
            temperature=0.3
        )

        texto = respuesta.choices[0].message.content
        objetos = [line.strip("-• \n") for line in texto.splitlines() if line.strip()]
        return objetos

    except Exception as e:
        st.error(f"Error en la detección: {e}")
        return []

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        img = Image.open(imagen)
        objetos = detectar_objetos_con_openai(img)

        if objetos:
            st.session_state.objetos_detectados = objetos
            st.success("✅ Objetos detectados por IA.")
        else:
            st.warning("❌ No se detectaron objetos.")

# === SELECCIÓN DE OBJETOS ===
if st.session_state.objetos_detectados:
    st.markdown("### 📦 Objetos detectados:")
    seleccionados = []
    for obj in st.session_state.objetos_detectados:
        if st.checkbox(obj, key=obj):
            seleccionados.append(obj)
    st.session_state.objetos_seleccionados = seleccionados

# === INICIAR CRONÓMETRO ===
if st.session_state.objetos_seleccionados:
    if not st.session_state.cronometro_activo:
        if st.button("▶️ Iniciar cronómetro"):
            st.session_state.inicio_sesion = datetime.now(tz)
            st.session_state.cronometro_activo = True
            st.rerun()

# === CRONÓMETRO EN CURSO ===
if st.session_state.cronometro_activo:
    inicio = st.session_state.inicio_sesion
    ahora = datetime.now(tz)
    segundos = int((ahora - inicio).total_seconds())
    st.success(f"🧭 Cronómetro en curso: {segundos} segundos")

    if segundos >= 120:
        if st.button("✅ Finalizar sesión"):
            doc = {
                "objetos": st.session_state.objetos_seleccionados,
                "timestamp": inicio,
                "duracion_segundos": segundos
            }
            col.insert_one(doc)
            st.session_state.cronometro_activo = False
            st.session_state.objetos_detectados = []
            st.session_state.objetos_seleccionados = []
            st.rerun()

# === HISTORIAL DE SESIONES ===
st.markdown("### 📚 Historial de sesiones")

registros = list(col.find().sort("timestamp", -1))

if registros:
    for reg in registros:
        fecha_raw = reg.get("timestamp")
        if fecha_raw:
            fecha = fecha_raw.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        else:
            fecha = "Fecha no disponible"

        st.markdown(f"**🕒 Fecha:** {fecha}")
        st.markdown(f"**⏱️ Duración:** {reg.get('duracion_segundos', 0)} segundos")
        st.markdown("**📦 Objetos:**")
        for i, obj in enumerate(reg.get("objetos", []), start=1):
            st.markdown(f"{i}. {obj}")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")