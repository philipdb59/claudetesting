import gradio as gr
import os
import matplotlib.pyplot as plt
import numpy as np
import time
import requests
import json

# Azure endpoint configuration
AZURE_ENDPOINT = os.environ.get("AZURE_ENDPOINT")
AZURE_API_KEY = os.environ.get("AZURE_API_KEY")

# Use the port specified by the environment variable WEBSITE_PORT, default to 7860 if not set.
port = int(os.environ.get("WEBSITE_PORT", 7860))

def chat_with_azure(message, history, file=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AZURE_API_KEY}",
        "Accept": "application/json"
    }

    # Konvertiere Gradio-History zu Azure-kompatibler History
    chat_history = []
    for i in range(0, len(history), 2):
        user_msg = history[i]["content"] if history[i]["role"] == "user" else ""
        bot_msg = history[i+1]["content"] if i+1 < len(history) and history[i+1]["role"] == "assistant" else ""
        chat_history.append({
            "inputs": {"question": user_msg},
            "outputs": {"answer": bot_msg}
        })

    payload = {
        "chat_input": message,
        "chat_history": chat_history
    }

    try:
        response = requests.post(AZURE_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        # 🔽 Hier holen wir die Antwort aus 'chat_output'
        answer = result.get("chat_output", "⚠️ Keine Antwort erhalten.")
        return answer
    except Exception as e:
        return f"❌ Fehler beim Aufruf des Azure-Endpoints: {str(e)}"

def handle_file(file):
    if file:
        return f"File {file.name} uploaded successfully."
    return ""

def generate_plot(message):
    x = np.linspace(0, 10, 100)
    y = np.sin(x) * len(message)
    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_title("Plot based on message length")
    return fig

# Create the chat interface with additional inputs for file upload
with gr.Blocks() as demo:
    chatbot = gr.ChatInterface(
        chat_with_azure,
        type="messages",
        flagging_mode="manual",
        flagging_options=["Like", "Spam", "Inappropriate", "Other"],
        save_history=True,
    )

    with gr.Accordion("Upload a File", open=False):
        file_upload = gr.File(label="Upload a File")
    plot_output = gr.Plot(label="Plot Output")

    clear = gr.Button("Clear")
    file_upload.change(handle_file, file_upload, chatbot, queue=False)
    clear.click(lambda: None, None, chatbot, queue=False)
    clear.click(lambda: None, None, plot_output, queue=False)

demo.launch(server_name="0.0.0.0", server_port=port)
