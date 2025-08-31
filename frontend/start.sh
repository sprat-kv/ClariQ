#!/bin/bash

# G-SIA Frontend Startup Script
# This script helps you quickly start the G-SIA system

echo "🚀 G-SIA Frontend Startup Script"
echo "=================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    echo "Please install Python 3 and try again"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "index.html" ]; then
    echo "❌ Please run this script from the frontend directory"
    echo "cd frontend && ./start.sh"
    exit 1
fi

echo "✅ Frontend files found"
echo ""

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Check if backend is running
echo "🔍 Checking backend status..."
if check_port 8000; then
    echo "✅ Backend is running on port 8000"
    BACKEND_RUNNING=true
else
    echo "⚠️  Backend is not running on port 8000"
    echo "   You'll need to start it separately"
    BACKEND_RUNNING=false
fi

echo ""

# Start frontend server
echo "🌐 Starting frontend server..."
echo "   Frontend will be available at: http://localhost:8080"
echo "   Demo page: http://localhost:8080/demo.html"
echo ""

# Check if port 8080 is available
if check_port 8080; then
    echo "⚠️  Port 8080 is already in use"
    echo "   Trying port 8081..."
    PORT=8081
else
    PORT=8080
fi

echo "📱 Starting frontend on port $PORT..."
echo "   Press Ctrl+C to stop the server"
echo ""

# Start Python HTTP server
python3 -m http.server $PORT

echo ""
echo "👋 Frontend server stopped"
echo ""
echo "💡 Tips:"
echo "   - Open http://localhost:$PORT in your browser"
echo "   - Check demo.html for feature overview"
echo "   - Ensure backend is running for full functionality"
echo ""