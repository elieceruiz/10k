import streamlit as st
import openai
from PIL import Image
import io
import base64

openai.api_key = st.secrets["openai_api_key"]

st.title("🔍 Detector de Objetos")

uploaded_file = st.file_uploader("📸 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    image_bytes = uploaded_file.read()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    # Prompt simple y claro
    prompt = f"Describe solo los objetos visibles en esta imagen. Sé conciso. Imagen (base64): {encoded_image}"

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # usa este para ahorrar tokens
            messages=[
                {"role": "system", "content": "Eres un asistente que detecta objetos en imágenes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0
        )
        resultado = response.choices[0].message.content
        st.success("✅ Objetos detectados:")
        st.write(resultado)

    except Exception as e:
        st.error(f"Error en la detección: {str(e)}")