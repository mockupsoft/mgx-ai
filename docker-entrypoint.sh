#!/bin/bash
set -e

# Create MetaGPT config directory and file
# This must happen BEFORE Python imports metagpt because Config validates at import time

METAGPT_DIR="$HOME/.metagpt"
METAGPT_CONFIG="$METAGPT_DIR/config2.yaml"

mkdir -p "$METAGPT_DIR"

# Determine LLM configuration based on LLM_DEFAULT_PROVIDER
echo "Creating MetaGPT config at $METAGPT_CONFIG..."
echo "LLM_DEFAULT_PROVIDER: ${LLM_DEFAULT_PROVIDER:-ollama}"

if [ "${LLM_DEFAULT_PROVIDER}" = "gemini" ]; then
    cat > "$METAGPT_CONFIG" << EOF
llm:
  api_type: gemini
  api_key: "${GOOGLE_API_KEY}"
  model: "${GEMINI_MODEL:-gemini-2.0-flash}"
EOF
elif [ "${LLM_DEFAULT_PROVIDER}" = "openrouter" ]; then
    cat > "$METAGPT_CONFIG" << EOF
llm:
  api_type: openai
  api_key: "${OPENROUTER_API_KEY}"
  base_url: "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
  model: "${OPENROUTER_MODEL:-nex-agi/deepseek-v3.1-nex-n1:free}"
EOF
elif [ "${LLM_DEFAULT_PROVIDER}" = "openai" ]; then
    cat > "$METAGPT_CONFIG" << EOF
llm:
  api_type: openai
  api_key: "${OPENAI_API_KEY}"
  base_url: ""
  model: "${OPENAI_MODEL:-gpt-4}"
EOF
elif [ "${LLM_DEFAULT_PROVIDER}" = "anthropic" ]; then
    cat > "$METAGPT_CONFIG" << EOF
llm:
  api_type: anthropic
  api_key: "${ANTHROPIC_API_KEY}"
  base_url: ""
  model: "${ANTHROPIC_MODEL:-claude-3-opus-20240229}"
EOF
else
    # Default to ollama
    cat > "$METAGPT_CONFIG" << EOF
llm:
  api_type: ollama
  api_key: ""
  base_url: "${OLLAMA_BASE_URL:-http://localhost:11434}"
  model: "${OLLAMA_MODEL:-llama3.2}"
EOF
fi

echo "MetaGPT config created:"
cat "$METAGPT_CONFIG"

# Set the config path environment variable
export METAGPT_CONFIG_PATH="$METAGPT_CONFIG"

# Execute the main command
exec "$@"

