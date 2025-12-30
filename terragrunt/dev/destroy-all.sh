#!/bin/bash

# Script to destroy all Terragrunt modules in reverse dependency order
# This bypasses dependency evaluation issues during destroy operations

set -e  # Exit on error

# Set environment variable to ignore dependency errors
export TERRAGRUNT_IGNORE_DEPENDENCY_ERRORS=true

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# List of modules in reverse dependency order (leaf nodes first)
MODULES=(
  "rag-embedder-lambda"
  "ecr-endpoints"
  "route53-internal"
  "rag-embedder"
  "rag-connector"
  "alb"
  "nlb"
  "qdrant"
  "ecs"
  "vpc"
)

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Terragrunt Destroy Script${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "${YELLOW}This will destroy all infrastructure in reverse dependency order.${NC}"
echo -e "${RED}WARNING: This is irreversible!${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
  echo "Destroy cancelled."
  exit 0
fi

# Track successes and failures
declare -a SUCCEEDED
declare -a FAILED

echo -e "${YELLOW}Starting destroy process...${NC}"
echo ""

for module in "${MODULES[@]}"; do
  if [ -d "$module" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Destroying: $module${NC}"
    echo -e "${YELLOW}========================================${NC}"

    cd "$module"

    # Try to destroy with Terragrunt
    if terragrunt destroy -auto-approve 2>&1 | tee /tmp/terragrunt-destroy-$module.log; then
      echo -e "${GREEN}✓ Successfully destroyed $module${NC}"
      SUCCEEDED+=("$module")
    else
      echo -e "${RED}✗ Failed to destroy $module${NC}"
      echo -e "${YELLOW}Attempting fallback: direct Terraform destroy...${NC}"

      # Fallback: try to find and use terraform directly in cache
      cache_dir=$(find . -type d -name ".terragrunt-cache" -maxdepth 1 2>/dev/null | head -1)
      if [ -n "$cache_dir" ]; then
        tf_dir=$(find "$cache_dir" -type f -name "terraform.tfstate" -exec dirname {} \; 2>/dev/null | head -1)
        if [ -n "$tf_dir" ]; then
          echo -e "${YELLOW}Found Terraform state in: $tf_dir${NC}"
          cd "$tf_dir"
          if terraform destroy -auto-approve; then
            echo -e "${GREEN}✓ Successfully destroyed $module via Terraform${NC}"
            SUCCEEDED+=("$module")
          else
            echo -e "${RED}✗ Failed to destroy $module even with Terraform${NC}"
            FAILED+=("$module")
          fi
          cd - > /dev/null
        else
          FAILED+=("$module")
        fi
      else
        FAILED+=("$module")
      fi
    fi

    cd ..
    echo ""
  else
    echo -e "${YELLOW}Module $module not found, skipping...${NC}"
    echo ""
  fi
done

# Summary
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Destroy Summary${NC}"
echo -e "${YELLOW}========================================${NC}"

if [ ${#SUCCEEDED[@]} -gt 0 ]; then
  echo -e "${GREEN}Successfully destroyed (${#SUCCEEDED[@]}):${NC}"
  for mod in "${SUCCEEDED[@]}"; do
    echo -e "  ${GREEN}✓${NC} $mod"
  done
  echo ""
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  echo -e "${RED}Failed to destroy (${#FAILED[@]}):${NC}"
  for mod in "${FAILED[@]}"; do
    echo -e "  ${RED}✗${NC} $mod"
  done
  echo ""
  echo -e "${YELLOW}For failed modules, you may need to:${NC}"
  echo -e "  1. Manually destroy resources in AWS Console"
  echo -e "  2. Remove state files: rm -rf $mod/.terragrunt-cache"
  echo -e "  3. Check logs in: /tmp/terragrunt-destroy-$mod.log"
  exit 1
else
  echo -e "${GREEN}All modules destroyed successfully!${NC}"
fi

echo ""
echo -e "${YELLOW}Cleaning up Terragrunt cache directories...${NC}"
read -p "Remove all .terragrunt-cache directories? (yes/no): " -r
if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
  find . -type d -name ".terragrunt-cache" -exec rm -rf {} + 2>/dev/null || true
  echo -e "${GREEN}Cache directories removed.${NC}"
fi

echo ""
echo -e "${GREEN}Destroy process complete!${NC}"
