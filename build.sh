#!/bin/bash
# Install Python packages
pip install -r requirements.txt

# Install tgpt binary
curl -sSfL https://raw.githubusercontent.com/aandrew-me/tgpt/main/install | bash -s /usr/local/bin

echo "✅ Build complete!"
