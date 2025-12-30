#!/bin/bash
# Package Lambda function for deployment

cd "$(dirname "$0")"

# Remove old zip if exists
rm -f lambda_function.zip

# Create new zip
zip lambda_function.zip lambda_function.py

echo "✓ Created lambda_function.zip"
echo ""
echo "Upload to AWS Lambda console or deploy with:"
echo "  aws lambda update-function-code --function-name rag-embedder-trigger --zip-file fileb://lambda_function.zip"
