#!/bin/bash
# Common git clone script for agent workers
# Usage: sourced by container-start.sh
# Assumes: workspace is empty
# Requires: REPOSITORY_URL, BRANCH, WORKSPACE environment variables
# Optional: GIT_USERNAME, GIT_TOKEN for private repositories

set -e

# Default values if not set
REPOSITORY_URL="${REPOSITORY_URL:-}"
BRANCH="${BRANCH:-main}"
WORKSPACE="${WORKSPACE:-/workspace}"
GIT_USERNAME="${GIT_USERNAME:-}"
GIT_TOKEN="${GIT_TOKEN:-}"

# Configure git credentials if provided
if [ -n "$GIT_USERNAME" ] && [ -n "$GIT_TOKEN" ]; then
    echo "Configuring git credentials..."
    git config --global credential.helper store
    echo "https://${GIT_USERNAME}:${GIT_TOKEN}@github.com" > ~/.git-credentials
fi

# Only proceed if repository URL is provided
if [ -z "$REPOSITORY_URL" ]; then
    echo "No repository URL provided, skipping clone"
    return 0
fi

echo "Setting up repository: $REPOSITORY_URL into $WORKSPACE..."

# First, verify the repository is accessible by attempting to fetch remote info
echo "Verifying repository accessibility..."
if git ls-remote "$REPOSITORY_URL" > /dev/null 2>&1; then
    echo "Repository is accessible: $REPOSITORY_URL"
else
    echo "Warning: Cannot access repository $REPOSITORY_URL"
    echo "Continuing anyway - this might be a network issue or invalid credentials"
fi

# Assume workspace is empty, clone repository
echo "Cloning repository into $WORKSPACE..."

# Try cloning with specified branch first
if git clone --depth 1 --branch "$BRANCH" "$REPOSITORY_URL" "$WORKSPACE" 2>/dev/null; then
    echo "Repository cloned successfully with branch $BRANCH"
else
    echo "Warning: Failed to clone with branch $BRANCH, trying fallback options..."
    
    # Try cloning without branch specification (use default branch)
    if git clone --depth 1 "$REPOSITORY_URL" "$WORKSPACE" 2>/dev/null; then
        echo "Repository cloned successfully using default branch"
        # Try to checkout the requested branch if it exists
        cd "$WORKSPACE"
        if git checkout "$BRANCH" 2>/dev/null; then
            echo "Checked out branch $BRANCH"
        else
            echo "Warning: Branch $BRANCH not found, using default branch"
            git checkout - || echo "Using current branch"
        fi
    else
        echo "Error: Failed to clone repository from $REPOSITORY_URL"
        echo "Please check the repository URL and your network connection"
        exit 1
    fi
fi

echo "Repository setup completed"
