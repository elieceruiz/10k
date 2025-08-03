import streamlit as st
from PIL import Image
from io import BytesIO
import base64
import openai
from pymongo import MongoClient
from datetime import datetime
import pytz
import time

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="👁️ Visión GPT – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT – Proyecto 10K")

# --- SECRETS Y CONEXIONES ---
openai.api_key = st.secrets["openai_api_key"]
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
tz = pytz.timezone("America/Bogota")

# --- FUNCIONES ---
def image_to_base64(img: Image.Image) -> str:
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def detectar_objetos(imagen: Image.Image) -> list:
    try:
        b64 = image_to_base64(imagen)
        prompt = "Enumera brevemente los objetos visibles en esta imagen como una lista en JSON, sin explicación."
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente que detecta objetos visuales."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": f"La imagen codificada es: {b64[:500]}..."}
            ],
            max_tokens=200,
            temperature=0.3
        )
        texto = respuesta.choices[0].message.content
        objetos = eval(texto)
        return objetos if isinstance(objetos, list) else []
    except Exception as e:
        st.error(f"Error en la detección: {e}")
        return []

# --- INTERFAZ ---
img = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if img:
    imagen = Image.open(img)
    st.image(imagen, caption="Imagen cargada", use_container_width=True)
    st.markdown("✅ Imagen cargada")

    if st.button("🔎 Detectar objetos"):
        objetos_detectados = detectar_objetos(imagen)

        if objetos_detectados:
            st.success("📦 Objetos detectados por IA")
            seleccionados = []
            for i, obj in enumerate(objetos_detectados, 1):
                if st.checkbox(f"{i}. {obj}"):
                    seleccionados.append(obj)

            if seleccionados:
                if st.button("🟢 Iniciar ordenamiento"):
                    inicio = datetime.now(tz)
                    marcador = st.empty()
                    segundos = 0

                    while True:
                        ahora = datetime.now(tz)
                        transcurrido = int((ahora - inicio).total_seconds())
                        marcador.markdown(f"🕒 Tiempo transcurrido: {transcurrido} segundos")
                        time.sleep(1)
                        segundos = transcurrido
                        st.session_state["tiempo"] = segundos
                        if segundos > 2:  # To break loop for testing
                            break

                    # --- Guardar en MongoDB ---
                    doc = {
                        "timestamp": datetime.now(tz),
                        "objetos": seleccionados,
                        "duracion_segundos": segundos
                    }
                    col.insert_one(doc)
                    st.success("📝 Sesión registrada exitosamente.")
        else:
            st.warning("❌ No se detectaron objetos.")

# --- HISTORIAL ---
with st.expander("📚 Historial de sesiones"):
    registros = list(col.find().sort("timestamp", -1).limit(10))
    if registros:
        for reg in registros:
            fecha = reg.get("timestamp", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            objs = ", ".join(reg.get("objetos", []))
            dur = reg.get("duracion_segundos", 0)
            st.markdown(f"• `{fecha}` — ⏱ {dur} seg — 🧩 {objs}")
    else:
        st.info("Sin registros aún.")