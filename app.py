import gradio as gr
import os
import pandas as pd
import requests
import io
import base64
import json
import re
from urllib.parse import quote

# Azure endpoint configuration
AZURE_ENDPOINT = os.environ.get("AZURE_ENDPOINT")
AZURE_API_KEY = os.environ.get("AZURE_API_KEY")
# PlantUML server URL - can be configured to use local JAR, server, or public PlantUML service
PLANTUML_SERVER = "http://www.plantuml.com/plantuml/png/"

# Use the port specified by the environment variable WEBSITE_PORT, default to 7860 if not set
port = int(os.environ.get("WEBSITE_PORT", 7860))

# Global variable to store the current PlantUML code
current_plantuml_code = ""

def encode_plantuml(plantuml_text):
    """Encode PlantUML text for use in the PlantUML server URL"""
    encoded = base64.b64encode(plantuml_text.encode('utf-8'))
    return quote(encoded.decode('utf-8'))

def process_file(file):
    """Extract requirements from uploaded CSV or XLSX file"""
    if file is None:
        return "No file uploaded", None
    
    try:
        file_extension = os.path.splitext(file.name)[1].lower()
        
        if file_extension == '.csv':
            df = pd.read_csv(file.name)
        elif file_extension == '.xlsx':
            df = pd.read_excel(file.name)
        else:
            return "Unsupported file format. Please upload a CSV or XLSX file.", None
        
        # Convert DataFrame to text for processing
        requirements_text = df.to_string(index=False)
        return "File processed successfully", requirements_text
    except Exception as e:
        return f"Error processing file: {str(e)}", None

def generate_plantuml_from_requirements(requirements_text):
    """Send requirements to Azure Prompt Flow to generate PlantUML code"""
    global current_plantuml_code
    
    if not requirements_text:
        return "No requirements provided", None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AZURE_API_KEY}",
        "Accept": "application/json"
    }
    
    # Create a payload with the system message instructing the model to generate PlantUML code
    payload = {
        "chat_input": "Generate PlantUML code for a requirements diagram based on this list: \n\n" + requirements_text,
        "chat_history": []
    }
    
    try:
        response = requests.post(AZURE_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        plantuml_code = result.get("chat_output", "No PlantUML code generated.")
        
        # Extract PlantUML code from the response if it's wrapped in code blocks
        code_block_pattern = r"```plantuml\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```"
        code_match = re.search(code_block_pattern, plantuml_code)
        
        if code_match:
            extracted_code = code_match.group(1) or code_match.group(2)
            current_plantuml_code = extracted_code.strip()
        else:
            # If no code block is found, assume the entire response is PlantUML code
            current_plantuml_code = plantuml_code
        
        # Validate that code contains essential PlantUML elements
        if "@startuml" not in current_plantuml_code:
            current_plantuml_code = "@startuml\n" + current_plantuml_code
        if "@enduml" not in current_plantuml_code:
            current_plantuml_code = current_plantuml_code + "\n@enduml"
        
        return "PlantUML code generated successfully", current_plantuml_code
    except Exception as e:
        return f"Error generating PlantUML code: {str(e)}", None

def render_plantuml(plantuml_code):
    """Render PlantUML code into a diagram image"""
    if not plantuml_code:
        return None
    
    try:
        # Encode the PlantUML code for use with the PlantUML server
        encoded = encode_plantuml(plantuml_code)
        image_url = f"{PLANTUML_SERVER}{encoded}"
        
        # Get the diagram image
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Create a file-like object from the image data
        image_data = io.BytesIO(response.content)
        
        return image_data
    except Exception as e:
        print(f"Error rendering PlantUML: {str(e)}")
        return None

def update_plantuml_with_chat(message, history):
    """Process user chat message to update the PlantUML diagram"""
    global current_plantuml_code
    
    if not current_plantuml_code:
        return "Please upload a requirements file first to generate a diagram."
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AZURE_API_KEY}",
        "Accept": "application/json"
    }
    
    # Convert Gradio chat history to a format suitable for the prompt
    chat_history_text = ""
    for i in range(0, len(history)):
        msg = history[i]
        prefix = "User: " if msg["role"] == "user" else "Assistant: "
        chat_history_text += f"{prefix}{msg['content']}\n"
    
    prompt = f"""
Current PlantUML code:
```
{current_plantuml_code}
```

User request: {message}

Based on the current PlantUML diagram and the user's request, generate updated PlantUML code that incorporates the requested changes.
Return only the complete, updated PlantUML code without any explanations.
"""
    
    payload = {
        "chat_input": prompt,
        "chat_history": []
    }
    
    try:
        response = requests.post(AZURE_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        updated_code = result.get("chat_output", "")
        
        # Extract PlantUML code from the response
        code_block_pattern = r"```plantuml\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```"
        code_match = re.search(code_block_pattern, updated_code)
        
        if code_match:
            extracted_code = code_match.group(1) or code_match.group(2)
            current_plantuml_code = extracted_code.strip()
        else:
            # If no code block is found, check if the response looks like PlantUML code
            if "@startuml" in updated_code or "requirement" in updated_code:
                current_plantuml_code = updated_code
        
        # Ensure the code has proper start and end tags
        if "@startuml" not in current_plantuml_code:
            current_plantuml_code = "@startuml\n" + current_plantuml_code
        if "@enduml" not in current_plantuml_code:
            current_plantuml_code = current_plantuml_code + "\n@enduml"
        
        # Render the updated diagram
        image_data = render_plantuml(current_plantuml_code)
        
        if image_data:
            return f"Diagram updated based on your request: '{message}'\n\nYou can download the updated diagram or PlantUML code using the buttons below."
        else:
            return f"Generated PlantUML code but failed to render diagram.\n\nUpdated PlantUML Code:\n```\n{current_plantuml_code}\n```"
            
    except Exception as e:
        return f"Error updating PlantUML diagram: {str(e)}"

def process_and_render(file):
    """Process uploaded file and render PlantUML diagram"""
    global current_plantuml_code
    
    status_msg, requirements_text = process_file(file)
    if not requirements_text:
        return status_msg, None, None
    
    status_msg, plantuml_code = generate_plantuml_from_requirements(requirements_text)
    if not plantuml_code:
        return status_msg, None, None
    
    image_data = render_plantuml(plantuml_code)
    if not image_data:
        return f"{status_msg}, but failed to render diagram", plantuml_code, None
    
    return status_msg, plantuml_code, image_data

def download_plantuml_code():
    """Return the current PlantUML code for download"""
    global current_plantuml_code
    return current_plantuml_code

def reset_all():
    """Reset all state variables and outputs"""
    global current_plantuml_code
    current_plantuml_code = ""
    return None, None, None, []

# Create the web application interface
with gr.Blocks(title="Requirements to PlantUML Diagram") as demo:
    gr.Markdown("# Requirements to PlantUML Diagram Generator")
    gr.Markdown("Upload a CSV or XLSX requirements file to generate a PlantUML diagram, then use chat to modify it.")
    
    with gr.Row():
        with gr.Column(scale=1):
            file_upload = gr.File(label="Upload Requirements File (CSV or XLSX)")
            status_output = gr.Textbox(label="Status", interactive=False)
            
            with gr.Row():
                process_btn = gr.Button("Generate Diagram", variant="primary")
                reset_btn = gr.Button("Reset", variant="secondary")
            
            with gr.Accordion("PlantUML Code", open=False):
                plantuml_code_output = gr.Code(language="plantuml", label="Generated PlantUML Code", interactive=False)
                download_code_btn = gr.Button("Download PlantUML Code")
            
        with gr.Column(scale=2):
            image_output = gr.Image(label="Generated Diagram", type="pil")
            download_img_btn = gr.Button("Download Diagram")
    
    gr.Markdown("## Chat to Modify the Diagram")
    gr.Markdown("Use natural language to request changes to the diagram (e.g., 'Add a requirement for user authentication' or 'Change the relationship between Req1 and Req2 to includes')")
    
    chatbot = gr.ChatInterface(
        update_plantuml_with_chat,
        type="messages",
        clear_ctx=reset_all,
        placeholder="Enter instructions to modify the diagram...",
        title="PlantUML Diagram Updates"
    )
    
    # Set up event handlers
    process_btn.click(
        process_and_render, 
        inputs=[file_upload], 
        outputs=[status_output, plantuml_code_output, image_output]
    )
    
    # Update diagram when chat sends a message
    chatbot.submit(
        render_plantuml,
        inputs=[plantuml_code_output],
        outputs=[image_output]
    )
    
    # Reset all state and outputs
    reset_btn.click(
        reset_all,
        inputs=None,
        outputs=[file_upload, plantuml_code_output, image_output, chatbot]
    )
    
    # Download handlers
    download_code_btn.click(
        download_plantuml_code,
        inputs=None,
        outputs=None,
        _js="""() => {
            const text = document.querySelector(".plantuml-code textarea").value;
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'plantuml_diagram.puml';
            a.click();
        }"""
    )
    
    download_img_btn.click(
        None,
        None,
        None,
        _js="""() => {
            const img = document.querySelector(".generated-diagram img");
            if (img) {
                const a = document.createElement('a');
                a.href = img.src;
                a.download = 'plantuml_diagram.png';
                a.click();
            }
        }"""
    )
    
demo.launch(server_name="0.0.0.0", server_port=port)
