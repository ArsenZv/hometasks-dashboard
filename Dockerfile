# Use a lightweight Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files into the container
COPY . /app

# Install the required dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 5555

# Define the command to run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5555", "app:app"]