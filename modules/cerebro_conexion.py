import google.generativeai as genai
import streamlit as st

def encender_ia():
    API_KEY = "AIzaSyCyGZN5L5Ywhl2qwfFF3ignyI51tD81CJc"
    genai.configure(api_key=API_KEY)
    try:
        # Busca el modelo más estable disponible en tu cuenta
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m_name in modelos:
            if '1.5-flash' in m_name:
                return genai.GenerativeModel(m_name)
        return genai.GenerativeModel(modelos[0])
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None