#!/bin/bash

# Update package lists
echo "Updating package lists..."
sudo apt-get update

# Install dependencies (example packages; modify as needed)
echo "Installing dependencies..."
sudo apt-get install -y python3 python3-pip git

# Download required models (example URLs; modify as needed)
echo "Downloading required models..."
wget -P ./models/ http://example.com/path/to/model1
wget -P ./models/ http://example.com/path/to/model2

# Set up a Python virtual environment
echo "Setting up the Python virtual environment..."
python3 -m venv env

# Activate the virtual environment
source env/bin/activate

# Install Python requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Setup complete!"