#!/bin/bash

echo "Cleaning up previous installations..."
# Remove any old cached versions or experimental shortcuts
rm -f ~/.local/share/applications/psp-media-suite.desktop
rm -f ~/.local/share/applications/vmg-psp-tool.desktop
rm -f ~/.local/share/icons/hicolor/512x512/apps/psp-media-suite*.png
rm -f ~/.local/share/icons/hicolor/512x512/apps/vmg-psp-icon.png
rm -f ~/.local/share/icons/psp-media-icon.png
rm -f ~/.local/bin/vmg-psp-tool
rm -f ~/.local/bin/psp-media-suite

echo "Installing PSP Media Suite v1.5..."

# Ensure standard Linux directories exist
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/512x512/apps

# 1. Copy the executable
if [ -f "app" ]; then
    cp app ~/.local/bin/psp-media-suite
    chmod +x ~/.local/bin/psp-media-suite
else
    echo "Error: Binary 'app' not found. Did you run 'cp dist/app .'?"
    exit 1
fi

# 2. Copy the icon (Using the new Icon.png)
if [ -f "Icon.png" ]; then
    cp Icon.png ~/.local/share/icons/hicolor/512x512/apps/psp-media-suite-icon.png
else
    echo "Warning: Icon.png not found in current directory."
fi

# 3. Generate the .desktop file
cat <<EOF > ~/.local/share/applications/psp-media-suite.desktop
[Desktop Entry]
Name=PSP Media Suite
Comment=Download and sync media directly to your PSP
Exec=$HOME/.local/bin/psp-media-suite
Icon=$HOME/.local/share/icons/hicolor/512x512/apps/psp-media-suite-icon.png
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
EOF

chmod +x ~/.local/share/applications/psp-media-suite.desktop

# 4. Refresh databases
touch ~/.local/share/icons/hicolor
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database ~/.local/share/applications
fi

echo "Installation Complete! PSP Media Suite is now in your app menu."
