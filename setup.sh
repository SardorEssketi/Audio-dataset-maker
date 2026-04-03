#!/bin/bash

echo "🎙️ Audio Pipeline Setup"
echo "======================="

# Create data directories
echo "Creating data directories..."
mkdir -p data/raw
mkdir -p data/normalized
mkdir -p data/denoised
mkdir -p data/vad_segments
mkdir -p data/transcriptions
mkdir -p models

# Create .gitkeep files
touch data/raw/.gitkeep
touch data/normalized/.gitkeep
touch data/denoised/.gitkeep
touch data/vad_segments/.gitkeep
touch data/transcriptions/.gitkeep
touch models/.gitkeep

echo "✅ Directories created"

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Ask about GPU
echo ""
read -p "Do you have CUDA GPU? (y/n): " has_gpu

# Install dependencies
echo ""
echo "Installing dependencies..."

if [ "$has_gpu" = "y" ] || [ "$has_gpu" = "Y" ]; then
    echo "Installing with CUDA support..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    echo "Installing CPU-only version..."
    pip install torch torchaudio
fi

pip install -r requirements.txt

echo ""
echo "✅ Dependencies installed"

# Check config
echo ""
if [ -f "config/config.yaml" ]; then
    echo "⚠️  Please edit config/config.yaml and set:"
    echo "   - huggingface.repo_id (your HF username/dataset-name)"
    echo "   - huggingface.token (your HF token or set HF_TOKEN env)"
    echo "   - whisper.language (ru, en, or auto)"
else
    echo "❌ config/config.yaml not found!"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/config.yaml"
echo "2. Run: python main.py --source <your_source>"
