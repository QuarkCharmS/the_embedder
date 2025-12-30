#!/bin/bash

# Force destroy script that bypasses Terragrunt dependency issues
# by directly using Terraform in the cached directories

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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
echo -e "${YELLOW}Force Destroy Script${NC}"
echo -e "${YELLOW}Using Terraform directly in cache dirs${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "${RED}WARNING: This will destroy all infrastructure!${NC}"
echo ""
read -p "Type 'yes' to continue: " -r
echo ""

if [[ ! $REPLY == "yes" ]]; then
  echo "Destroy cancelled."
  exit 0
fi

declare -a SUCCEEDED
declare -a FAILED
declare -a SKIPPED

for module in "${MODULES[@]}"; do
  echo -e "${YELLOW}========================================${NC}"
  echo -e "${YELLOW}Processing: $module${NC}"
  echo -e "${YELLOW}========================================${NC}"

  if [ ! -d "$module" ]; then
    echo -e "${YELLOW}Module directory not found, skipping...${NC}"
    SKIPPED+=("$module")
    echo ""
    continue
  fi

  cd "$module"

  # Find the most recent Terragrunt cache directory
  cache_dir=$(find . -type d -name ".terragrunt-cache" -maxdepth 1 2>/dev/null | head -1)

  if [ -z "$cache_dir" ]; then
    echo -e "${YELLOW}No cache directory found. Trying to init...${NC}"

    # Try to initialize without dependency resolution
    export TERRAGRUNT_IGNORE_DEPENDENCY_ERRORS=true
    if terragrunt init 2>&1 | grep -q "Error"; then
      echo -e "${RED}Failed to initialize. Skipping $module${NC}"
      SKIPPED+=("$module")
      cd ..
      echo ""
      continue
    fi

    cache_dir=$(find . -type d -name ".terragrunt-cache" -maxdepth 1 2>/dev/null | head -1)
  fi

  if [ -n "$cache_dir" ]; then
    # Find the actual Terraform working directory
    tf_dir=$(find "$cache_dir" -type d -name ".terraform" 2>/dev/null | head -1)

    if [ -n "$tf_dir" ]; then
      # Go to the parent directory of .terraform
      work_dir=$(dirname "$tf_dir")
      echo -e "${GREEN}Found Terraform directory: $work_dir${NC}"

      cd "$work_dir"

      # Check if state exists
      if [ -f "terraform.tfstate" ] || terraform state list &>/dev/null; then
        echo -e "${YELLOW}Destroying resources...${NC}"

        # Extract variable names from .tf files and create dummy values
        echo -e "${YELLOW}Generating variable overrides...${NC}"

        # Start building the var flags
        VAR_FLAGS="-auto-approve"

        # Find all variable declarations and create dummy values
        if ls *.tf &>/dev/null; then
          while IFS= read -r varname; do
            # Skip if varname is empty
            [ -z "$varname" ] && continue

            # Check variable type and provide appropriate dummy value
            if grep -A 3 "^variable \"$varname\"" *.tf 2>/dev/null | grep -q "type.*=.*list"; then
              VAR_FLAGS="$VAR_FLAGS -var='${varname}=[\"dummy1\",\"dummy2\"]'"
            elif grep -A 3 "^variable \"$varname\"" *.tf 2>/dev/null | grep -q "type.*=.*map"; then
              VAR_FLAGS="$VAR_FLAGS -var='${varname}={}'"
            elif grep -A 3 "^variable \"$varname\"" *.tf 2>/dev/null | grep -q "type.*=.*number"; then
              VAR_FLAGS="$VAR_FLAGS -var='${varname}=0'"
            elif grep -A 3 "^variable \"$varname\"" *.tf 2>/dev/null | grep -q "type.*=.*bool"; then
              VAR_FLAGS="$VAR_FLAGS -var='${varname}=false'"
            else
              VAR_FLAGS="$VAR_FLAGS -var='${varname}=dummy'"
            fi
          done < <(grep -h '^variable ' *.tf 2>/dev/null | sed 's/variable "\([^"]*\)".*/\1/')
        fi

        # Try to destroy with generated var flags
        if eval "terraform destroy $VAR_FLAGS" 2>&1; then
          echo -e "${GREEN}✓ Successfully destroyed $module${NC}"
          SUCCEEDED+=("$module")
        else
          echo -e "${RED}✗ Terraform destroy failed for $module${NC}"
          FAILED+=("$module")
        fi
      else
        echo -e "${YELLOW}No state found for $module, skipping...${NC}"
        SKIPPED+=("$module")
      fi

      cd - > /dev/null
    else
      echo -e "${YELLOW}No Terraform directory found in cache for $module${NC}"
      SKIPPED+=("$module")
    fi
  else
    echo -e "${YELLOW}Could not find or create cache for $module${NC}"
    SKIPPED+=("$module")
  fi

  cd ..
  echo ""
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
fi

if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo -e "${YELLOW}Skipped (${#SKIPPED[@]}):${NC}"
  for mod in "${SKIPPED[@]}"; do
    echo -e "  ${YELLOW}⊘${NC} $mod"
  done
  echo ""
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  echo -e "${RED}Some modules failed to destroy.${NC}"
  echo -e "${YELLOW}Next steps:${NC}"
  echo -e "  1. Check AWS Console for remaining resources"
  echo -e "  2. Use AWS CLI to delete resources manually"
  echo -e "  3. Then clean up: rm -rf */.terragrunt-cache"
  exit 1
fi

echo -e "${GREEN}All modules processed!${NC}"
