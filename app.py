import streamlit as st
import openai
import base64
import requests
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
import os
from pymongo import MongoClient

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="👁️ Visión 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA VARIABLES DE ENTORNO ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
mongo_uri = os.getenv("MONGO_URI")

# === CONEXIÓN CON MONGODB ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["detecciones_10k"]

# === CONSULTAR SALDO OPENAI ===
def get_credit_balance():
    headers = {"Authorization": f"Bearer {openai.api_key}"}
    try:
        resp = requests.get("https://api.openai.com/v1/dashboard/billing/credit_grants", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data["total_available"]
        else:
            return "No disponible"
    except:
        return "Error"

# === SUBIR IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_column_width=True)
    username = st.text_input("🧍 Tu nombre (opcional):", "eliecer")

    # Convertir imagen a base64
    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === CONSULTAR GPT-4o CON VISIÓN ===
    with st.spinner("Analizando con GPT-4o..."):
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

    # === REGISTRAR EN MONGODB ===
    doc = {
        "usuario": username,
        "fecha": datetime.utcnow(),
        "descripcion": result,
        "nombre_imagen": uploaded_file.name,
        "saldo_openai": get_credit_balance()
    }
    col.insert_one(doc)
    st.success("✅ Registro guardado en MongoDB")

# === MOSTRAR SALDO ===
st.divider()
st.subheader("💳 Saldo OpenAI disponible:")
saldo = get_credit_balance()
st.write(f"**{saldo} USD**" if isinstance(saldo, float) else saldo)