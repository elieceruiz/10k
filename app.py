import streamlit as st
import openai
import base64
import requests
from datetime import datetime
from pymongo import MongoClient

# === CONFIGURACIÓN DE LA APP ===
st.set_page_config(page_title="👁️ Visión 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGAR CREDENCIALES DESDE st.secrets ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONECTAR A MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["detecciones_10k"]

# === FUNCIÓN PARA CONSULTAR SALDO DE OPENAI ===
@st.cache_data(ttl=600)
def get_credit_balance():
    try:
        headers = {"Authorization": f"Bearer {openai.api_key}"}
        response = requests.get("https://api.openai.com/v1/dashboard/billing/credit_grants", headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("total_available", "No disponible")
        return "No disponible"
    except Exception as e:
        return f"Error: {str(e)}"

# === CARGAR IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    username = st.text_input("🧍 Tu nombre (opcional):", "eliecer")

    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === CONSULTAR GPT-4o CON VISIÓN ===
    with st.spinner("Analizando imagen con GPT-4o..."):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un asistente que describe con detalle lo que ve en una imagen."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "¿Qué ves en esta imagen?"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=300
            )
            result = response.choices[0].message.content
            st.success("🔎 Resultado del análisis:")
            st.write(result)

            # === REGISTRAR EN MONGO ===
            doc = {
                "usuario": username,
                "fecha": datetime.utcnow(),
                "descripcion": result,
                "nombre_imagen": uploaded_file.name,
                "saldo_openai": get_credit_balance()
            }
            col.insert_one(doc)
            st.info("✅ Registro guardado en MongoDB")

        except Exception as e:
            st.error(f"❌ Error al analizar la imagen: {str(e)}")

# === MOSTRAR SALDO DISPONIBLE ===
st.divider()
st.subheader("💳 Saldo restante en OpenAI:")
saldo = get_credit_balance()
st.write(f"**{saldo} USD**" if isinstance(saldo, float) else saldo)

# === MOSTRAR HISTORIAL DE REGISTROS ===
st.divider()
st.subheader("📚 Historial de análisis anteriores:")

registros = list(col.find().sort("fecha", -1))
if registros:
    for r in registros[:10]:  # Mostrar solo los últimos 10
        st.markdown(f"**🧍 Usuario:** {r.get('usuario', 'Desconocido')}")
        st.markdown(f"🕒 **Fecha:** {r['fecha'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        st.markdown(f"📝 **Descripción:** {r['descripcion']}")
        st.markdown(f"💳 **Saldo en ese momento:** {r.get('saldo_openai', 'N/A')} USD")
        st.markdown("---")
else:
    st.info("No hay registros aún.")