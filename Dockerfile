FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files
COPY . .

# Install the dependencies from requirements.txt
RUN pip install -r requirements.txt

# Set environment variables
ENV FLASK_APP app.py
ENV FLASK_ENV production
ENV SECRET_KEY="change_me_later"

# Expose the port the app runs on
EXPOSE 5000

# Run the application using gunicorn as the WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]