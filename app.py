import streamlit as st
import openai
from PIL import Image
import base64
import io

# CONFIG
st.set_page_config(page_title="Visión IA – 10K", layout="centered")
st.title("📸 Detección de Objetos – Proyecto 10K")
openai.api_key = st.secrets["openai_api_key"]

# Función para convertir imagen a base64
def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    return base64.b64encode(img_bytes).decode()

# Procesamiento
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["png", "jpg", "jpeg"])

if uploaded_file:
    imagen = Image.open(uploaded_file)
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos con IA"):
        try:
            base64_image = pil_to_base64(imagen)
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Detecta y lista los objetos visibles en esta imagen, solo como palabras, sin explicaciones."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ],
                    }
                ],
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip()
            objetos = [o.strip(" .,-") for o in result.split(",") if o.strip()]
            if objetos:
                st.success("✅ Objetos detectados:")
                for i, obj in enumerate(objetos, 1):
                    st.checkbox(f"{i}. {obj}", key=f"obj_{i}")
            else:
                st.warning("No se detectaron objetos útiles.")

        except Exception as e:
            st.error(f"❌ Error: {e}")