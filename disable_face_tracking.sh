#!/bin/bash

# Script to disable face tracking on Ubuntu server
# This helps avoid MediaPipe errors on servers without proper graphics support

echo "🔧 Disabling face tracking to prevent MediaPipe errors on Ubuntu server..."

# Add environment variable to disable face tracking
export DISABLE_FACE_TRACKING=true

# Add to systemd service if it exists
if [ -f "/etc/systemd/system/aiclips-backend.service" ]; then
    echo "📝 Adding DISABLE_FACE_TRACKING to systemd service..."
    
    # Backup original service file
    sudo cp /etc/systemd/system/aiclips-backend.service /etc/systemd/system/aiclips-backend.service.backup
    
    # Add environment variable to service
    if ! grep -q "Environment=DISABLE_FACE_TRACKING=true" /etc/systemd/system/aiclips-backend.service; then
        sudo sed -i '/\[Service\]/a Environment=DISABLE_FACE_TRACKING=true' /etc/systemd/system/aiclips-backend.service
        echo "✅ Added DISABLE_FACE_TRACKING to systemd service"
        
        # Reload systemd and restart service
        sudo systemctl daemon-reload
        echo "🔄 Reloading systemd daemon..."
        
        echo "⚠️  To restart the service with face tracking disabled, run:"
        echo "    sudo systemctl restart aiclips-backend"
    else
        echo "✅ DISABLE_FACE_TRACKING already exists in systemd service"
    fi
else
    echo "⚠️  Systemd service file not found at /etc/systemd/system/aiclips-backend.service"
    echo "💡 You can manually set the environment variable:"
    echo "    export DISABLE_FACE_TRACKING=true"
    echo "    python run.py"
fi

# Add to .env file if it exists
if [ -f ".env" ]; then
    if ! grep -q "DISABLE_FACE_TRACKING=true" .env; then
        echo "DISABLE_FACE_TRACKING=true" >> .env
        echo "✅ Added DISABLE_FACE_TRACKING to .env file"
    else
        echo "✅ DISABLE_FACE_TRACKING already exists in .env file"
    fi
else
    echo "📝 Creating .env file with DISABLE_FACE_TRACKING=true"
    echo "DISABLE_FACE_TRACKING=true" > .env
fi

echo ""
echo "🎯 Face tracking has been disabled!"
echo "📋 This will:"
echo "   • Prevent MediaPipe initialization errors"
echo "   • Skip face detection during video processing"
echo "   • Use fallback cropping (upper-third crop) instead"
echo "   • Improve stability on Ubuntu servers"
echo ""
echo "🔄 Restart your backend service to apply changes"
