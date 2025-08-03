import streamlit as st
from pymongo import MongoClient
import openai
from PIL import Image
import io
import time
import pytz
from datetime import datetime
import base64  # ← NECESARIO

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETS ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === FUNCIONES ===

def detectar_objetos_con_gpt(image):
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente que identifica objetos visibles en imágenes, responde SOLO con una lista de objetos detectados, sin explicaciones."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "¿Qué objetos hay en esta imagen? Solo responde con una lista separada por comas."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                    ]
                }
            ],
            max_tokens=150
        )

        resultado = response.choices[0].message.content
        lista_objetos = [obj.strip() for obj in resultado.split(",") if obj.strip()]
        return lista_objetos

    except Exception as e:
        return f"Error en la detección: {str(e)}"


# === INTERFAZ PRINCIPAL ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    with st.spinner("Analizando imagen..."):
        image_pil = Image.open(imagen)
        objetos = detectar_objetos_con_gpt(image_pil)

    if isinstance(objetos, list) and objetos:
        st.success("✅ Objetos detectados por IA.")
        st.subheader("📦 Objetos detectados:")
        objeto_check = {}
        for i, obj in enumerate(objetos, start=1):
            objeto_check[obj] = st.checkbox(f"{i}. {obj}")

        orden_seleccionado = []
        for obj in objetos:
            if objeto_check.get(obj):
                orden_seleccionado.append(obj)

        if orden_seleccionado:
            if st.button("▶️ Iniciar cronómetro"):
                st.session_state["inicio"] = time.time()
                st.session_state["objetos_en_orden"] = orden_seleccionado
                st.rerun()

    elif isinstance(objetos, str) and objetos.startswith("Error"):
        st.error(objetos)
    else:
        st.warning("❌ No se detectaron objetos.")

# === CRONÓMETRO POR OBJETO ===
if "inicio" in st.session_state and "objetos_en_orden" in st.session_state:
    tiempo_actual = time.time()
    tiempo_transcurrido = int(tiempo_actual - st.session_state["inicio"])
    st.markdown(f"⏱️ **Tiempo total transcurrido:** {tiempo_transcurrido} segundos")

    st.subheader("🏷️ Objetos en orden de ubicación:")
    for idx, obj in enumerate(st.session_state["objetos_en_orden"], start=1):
        st.markdown(f"{idx}. {obj}")

    if tiempo_transcurrido >= 120:
        if st.button("✅ Finalizar sesión"):
            doc = {
                "timestamp": datetime.now(tz),
                "objetos": st.session_state["objetos_en_orden"],
                "duracion_segundos": tiempo_transcurrido
            }
            col.insert_one(doc)
            st.success("📝 Sesión registrada con éxito.")
            del st.session_state["inicio"]
            del st.session_state["objetos_en_orden"]
            st.rerun()

# === HISTORIAL DE SESIONES ===
st.subheader("📚 Historial de sesiones")

registros = list(col.find().sort("timestamp", -1))

if registros:
    for reg in registros:
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🕒 Fecha:** {fecha}")
        st.markdown(f"**⏱️ Duración:** {reg.get('duracion_segundos', 0)} segundos")
        st.markdown("**📦 Objetos:**")
        for i, obj in enumerate(reg.get("objetos", []), start=1):
            st.markdown(f"{i}. {obj}")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")