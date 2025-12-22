#!/bin/bash
# Build script for sandbox base images

set -e

echo "🏗️  Building MGX Sandbox Base Images"

# Function to build and tag image
build_image() {
    local dockerfile=$1
    local tag=$2
    local image_name=$3
    
    echo "📦 Building ${image_name}..."
    docker build -f ${dockerfile} -t ${tag} .
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully built ${image_name}"
        docker tag ${tag} ${tag}:latest
        
        # Show image info
        echo "📊 Image info:"
        docker images ${tag} --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    else
        echo "❌ Failed to build ${image_name}"
        exit 1
    fi
}

# Build Python sandbox image
build_image "sandbox/images/Dockerfile.python" "mgx-sandbox-python:latest" "Python 3.10 Sandbox"

# Build Node.js sandbox image  
build_image "sandbox/images/Dockerfile.node" "mgx-sandbox-node:latest" "Node.js 18 Sandbox"

# Build PHP sandbox image
build_image "sandbox/images/Dockerfile.php" "mgx-sandbox-php:latest" "PHP 8.1 Sandbox"

echo ""
echo "🎉 All sandbox images built successfully!"
echo ""
echo "📋 Available images:"
echo "  - mgx-sandbox-python:latest (Python 3.10 + pytest + testing tools)"
echo "  - mgx-sandbox-node:latest (Node.js 18 + npm/yarn + testing frameworks)"  
echo "  - mgx-sandbox-php:latest (PHP 8.1 + composer + phpunit)"
echo ""
echo "🚀 Usage:"
echo "  python -m backend.scripts.seed_sandbox_images --workspace-id <id>"
echo ""
echo "🔍 Verify images:"
echo "  docker images | grep mgx-sandbox"