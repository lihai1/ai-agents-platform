FROM agentic-agents-platform-agent-worker-base-builder:latest

WORKDIR /app
# The base-builder image already provides /app/pyproject.toml and uv.
# Copy the worker source and install the unified agent-worker package.
COPY services/agent-worker/internal /app/internal
RUN uv pip install --system --no-cache -e "/app"

# Install Playwright browser for web search / browser automation
RUN playwright install chromium

ENV AGENT_TYPE=specialist

# Chunking defaults for terminal output streaming
ENV OUTPUT_MAX_BUFFER_CHARS=8000
ENV CHUNK_SIZE_BYTES=2500

# Defaults for the crewai-expert flow
ENV CREWAI_EXPERT_REPAIR=true
ENV CREWAI_EXPERT_REQUIRE_PATCH_APPROVAL=true
ENV CREWAI_EXPERT_MAX_SELECTION_ATTEMPTS=3
ENV CREWAI_EXPERT_MAX_PATCH_ATTEMPTS=2
ENV OLLAMA_BASE_URL=http://localhost:11434
ENV MODEL_NAME=qwen3.5:9b

CMD ["/app/container-start.sh"]
