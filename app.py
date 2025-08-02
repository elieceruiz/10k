import streamlit as st
import pymongo
import base64
import io
from datetime import datetime
from PIL import Image
import requests
import os

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="🧹 10.000 – Orden Personal", layout="centered")
st.title("🧹 10.000 – Orden Personal")

# === CONEXIÓN A MONGODB ATLAS ===
MONGO_URI = os.environ.get("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["orden_db"]
coleccion = db["orden_sesiones"]

# === Función auxiliar para codificar imagen ===
def image_file_to_base64(image_file):
    img = Image.open(image_file).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode(), img

# === Enviar imagen a Roboflow vía API REST ===
def detectar_objetos_con_roboflow(image_file):
    ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY")
    MODEL_ID = os.environ.get("ROBOFLOW_MODEL_ID")
    url = f"https://detect.roboflow.com/{MODEL_ID}?api_key={ROBOFLOW_API_KEY}"

    image_bytes = image_file.read()
    response = requests.post(url, files={"file": image_bytes})
    result = response.json()

    # DEBUG opcional (comentá si no lo usás)
    # st.subheader("🛠 Respuesta completa de Roboflow")
    # st.json(result)

    etiquetas = [pred["class"] for pred in result.get("predictions", [])]
    return list(set(etiquetas))

# === CAPTURA DE IMAGEN ===
foto = st.camera_input("📸 Tomá una foto del espacio a ordenar")

if foto:
    base64_img, img_pil = image_file_to_base64(foto)
    st.image(img_pil, caption="Imagen capturada", use_container_width=True)

    try:
        etiquetas = detectar_objetos_con_roboflow(foto)

        if etiquetas:
            st.success(f"✅ {len(etiquetas)} objeto(s) detectado(s). Seleccioná hasta 3 para registrar:")
            objetos_trabajados = []
            for etiqueta in etiquetas:
                if len(objetos_trabajados) < 3 and st.checkbox(etiqueta, key=etiqueta):
                    destino = st.selectbox(
                        f"¿Dónde fue '{etiqueta}'?",
                        ["Ganchos", "Reciclaje", "Cajón tech", "Estante", "Donación", "Basura"],
                        key=f"destino_{etiqueta}"
                    )
                    objetos_trabajados.append({"nombre": etiqueta, "destino": destino})

            if st.button("💾 Guardar sesión"):
                if objetos_trabajados:
                    doc = {
                        "timestamp": datetime.utcnow(),
                        "image_base64": base64_img,
                        "objetos_detectados": etiquetas,
                        "objetos_trabajados": objetos_trabajados
                    }
                    coleccion.insert_one(doc)
                    st.success("🧾 Sesión registrada correctamente.")
                else:
                    st.warning("⚠️ Seleccioná al menos un objeto para registrar.")
        else:
            st.warning("🕵️‍♂️ No se detectaron objetos en la imagen. Probá otra foto con objetos más visibles o mejor iluminados.")

    except Exception as e:
        st.error(f"❌ Error al procesar la imagen: {e}")