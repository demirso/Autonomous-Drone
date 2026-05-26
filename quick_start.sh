#!/bin/bash

# Quick Start Setup Script for Autonomous Quadcopter

echo "=== Autonomous Quadcopter - Quick Start Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p logs

# Verify files exist
echo ""
echo "Verifying project files..."
files=("flight_controller.py" "stabilization_controller.py" "config.py" "requirements.txt" "README.md")

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ $file (MISSING)"
    fi
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Read the README.md file"
echo "2. Review SAFETY WARNINGS"
echo "3. Connect Pixhawk via USB"
echo "4. Run: python3 flight_controller.py --test-sensors"
echo ""

