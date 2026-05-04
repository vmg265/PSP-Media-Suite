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

echo "Installing PSP Media Suite..."

# Ensure standard Linux directories exist
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/512x512/apps

# 1. Copy the executable
cp app ~/.local/bin/psp-media-suite
chmod +x ~/.local/bin/psp-media-suite

# 2. Copy the icon into the strict hicolor theme folder
cp icon.png ~/.local/share/icons/hicolor/512x512/apps/psp-media-suite-icon.png

# 3. Generate the .desktop file using the absolute path
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

# 4. Force Linux to rebuild the icon and desktop databases
touch ~/.local/share/icons/hicolor
update-desktop-database ~/.local/share/applications

echo "Installation Complete! You can now find PSP Media Suite in your application menu."