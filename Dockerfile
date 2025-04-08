# Use an official Python 3.10 slim image
FROM python:3.10-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Expose the port that Gradio will run on (use the same port as in app.py)
EXPOSE 7860

# Set the GRADIO_SERVER_NAME environment variable to ensure Gradio listens on all interfaces
ENV GRADIO_SERVER_NAME="0.0.0.0"

# Start the Gradio app
CMD ["python", "app.py"]
