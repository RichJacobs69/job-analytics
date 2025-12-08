#!/bin/bash
# Setup script for Claude Code in Cursor

# Add Node.js to PATH permanently
echo 'export PATH="$HOME/.nodejs/bin:$PATH"' >> ~/.zshrc

# Source the updated profile
source ~/.zshrc

echo "Claude Code setup complete!"
echo "You can now use 'claude' command in your terminal."
