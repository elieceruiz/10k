import streamlit as st
from datetime import datetime
from pymongo import MongoClient
import pytz
import openai
from PIL import Image
import io
import base64
import time

# === CONFIGURACIÓN DE LA APP ===
st.set_page_config(page_title="👁️ Visión GPT – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETS & ZONA HORARIA ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_KEY = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === MONGO CLIENT ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# === OPENAI KEY ===
openai.api_key = OPENAI_KEY

# === FUNCIONES AUXILIARES ===
def analizar_imagen_con_openai(image_bytes):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente que detecta objetos comunes en una habitación."},
                {"role": "user", "content": "Analiza esta imagen y devuélveme una lista en JSON con solo los nombres de los objetos visibles."}
            ],
            max_tokens=300,
            temperature=0,
            tools=[{
                "type": "image",
                "image": image_bytes
            }]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error en la detección: {e}"

def guardar_registro(objetos, duracion_segundos, imagen_bytes):
    doc = {
        "timestamp": datetime.now(tz),
        "objetos": objetos,
        "duracion_segundos": duracion_segundos,
        "imagen": base64.b64encode(imagen_bytes).decode()
    }
    col.insert_one(doc)

def mostrar_historial():
    st.subheader("📜 Historial de Sesiones")
    registros = list(col.find().sort("timestamp", -1))
    for i, reg in enumerate(registros):
        tiempo = reg.get("duracion_segundos", 0)
        mins, segs = divmod(tiempo, 60)
        tiempo_fmt = f"{mins:02d}:{segs:02d}"
        objetos = ", ".join(reg.get("objetos", []))
        if "timestamp" in reg:
            fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        else:
            fecha = "Sin fecha"
        st.markdown(f"**{i+1}.** `{fecha}` – ⏱ {tiempo_fmt} – 📦 {objetos}")

# === APP FLOW ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    image_bytes = uploaded_file.read()

    if st.button("🔍 Detectar objetos"):
        with st.spinner("Analizando imagen..."):
            resultado = analizar_imagen_con_openai(image_bytes)

        try:
            objetos_detectados = eval(resultado)  # 👈 asegúrate que OpenAI devuelva una lista
            if isinstance(objetos_detectados, list):
                st.success("✅ Objetos detectados por IA.")
                st.markdown("📦 **Objetos detectados:**")
                seleccionados = []
                for obj in objetos_detectados:
                    if st.checkbox(obj):
                        seleccionados.append(obj)

                if seleccionados:
                    st.markdown("🕒 Selecciona el orden y presiona Iniciar:")
                    if st.button("▶️ Iniciar sesión"):
                        tiempo_inicio = time.time()
                        while True:
                            tiempo_actual = int(time.time() - tiempo_inicio)
                            mins, segs = divmod(tiempo_actual, 60)
                            st.metric("⏱ Tiempo transcurrido", f"{mins:02d}:{segs:02d}")
                            time.sleep(1)
                            st.rerun()

                        guardar_registro(seleccionados, tiempo_actual, image_bytes)
                        st.success("✅ Registro guardado exitosamente.")
            else:
                st.warning("⚠️ No se pudo interpretar la respuesta de la IA.")
        except Exception as e:
            st.error(f"❌ Error al procesar: {e}")

# === MOSTRAR HISTORIAL ===
mostrar_historial()