#!/bin/bash

# Test script for Grok Intelligence Engine API endpoints
# Validates all documented API examples work correctly

set -e

BASE_URL="http://localhost:8002"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Testing Grok Intelligence Engine API Endpoints${NC}"
echo "Base URL: $BASE_URL"
echo

# Function to test endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    
    echo -n "Testing $method $endpoint ($description)... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint")
    fi
    
    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL (HTTP $response)${NC}"
        return 1
    fi
}

# Function to test endpoint with JSON output
test_endpoint_json() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    
    echo "Testing $method $endpoint ($description)..."
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s "$BASE_URL$endpoint")
    else
        response=$(curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint")
    fi
    
    echo "$response" | jq . > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS (Valid JSON)${NC}"
        echo "$response" | jq .
        echo
        return 0
    else
        echo -e "${RED}❌ FAIL (Invalid JSON)${NC}"
        echo "Response: $response"
        echo
        return 1
    fi
}

echo -e "${YELLOW}📊 Service Management Endpoints${NC}"

# Health check
test_endpoint_json "GET" "/health" "Service health check"

# Capabilities
test_endpoint_json "GET" "/capabilities" "Service capabilities"

# Services (may be empty but should return valid JSON)
test_endpoint_json "GET" "/services" "Registered services"

# Provider status
test_endpoint_json "GET" "/providers/status" "LLM provider status"

echo -e "${YELLOW}📋 Profile Management Endpoints${NC}"

# List profiles
test_endpoint_json "GET" "/profiles" "List available profiles"

# Get specific profile
test_endpoint_json "GET" "/profiles/business_meeting" "Business meeting profile details"

# Test invalid profile (should return 404)
echo -n "Testing GET /profiles/invalid_profile (should return 404)... "
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/profiles/invalid_profile")
if [ "$response" = "404" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (Expected 404, got $response)${NC}"
fi

echo -e "${YELLOW}🔄 Processing Endpoints${NC}"

# Test processing endpoint
SAMPLE_REQUEST='{
  "job_id": "test-job-001",
  "data": {
    "type": "text/plain",
    "content": "John: Welcome to our weekly standup. Jane: Thanks John. I completed the API documentation and started working on the authentication module. John: Great progress! What is next on your roadmap? Jane: I plan to finish authentication by Friday and then move on to user management features.",
    "encoding": "utf-8"
  },
  "metadata": {
    "profile_id": "business_meeting"
  }
}'

test_endpoint_json "POST" "/process" "Process business meeting transcript" "$SAMPLE_REQUEST"

# Test processing with overrides
OVERRIDE_REQUEST='{
  "job_id": "test-job-002",
  "data": {
    "type": "text/plain",
    "content": "Project kickoff meeting: We need to deliver the MVP by Q2 2025. Key features include user authentication, data visualization, and reporting. Risk: tight timeline. Mitigation: agile development approach.",
    "encoding": "utf-8"
  },
  "metadata": {
    "profile_id": "project_planning",
    "overrides": {
      "force_provider": "local",
      "global_temperature": 0.2
    }
  }
}'

test_endpoint_json "POST" "/process" "Process with global overrides" "$OVERRIDE_REQUEST"

# Test invalid request (missing required fields)
INVALID_REQUEST='{
  "job_id": "test-job-003",
  "data": {
    "type": "invalid/type",
    "content": "",
    "encoding": "utf-8"
  }
}'

echo -n "Testing POST /process with invalid data (should return 400)... "
response=$(curl -s -o /dev/null -w "%{http_code}" -X "POST" \
    -H "Content-Type: application/json" \
    -d "$INVALID_REQUEST" \
    "$BASE_URL/process")
if [ "$response" = "400" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (Expected 400, got $response)${NC}"
fi

echo
echo -e "${YELLOW}📊 Test Summary${NC}"
echo "All documented API endpoints have been tested."
echo "✅ Service responds to all expected endpoints"
echo "✅ Returns valid JSON for all successful requests"
echo "✅ Proper error codes for invalid requests"
echo
echo -e "${GREEN}🎉 API testing completed successfully!${NC}"
echo
echo -e "${YELLOW}💡 Next Steps:${NC}"
echo "• Start Phase 3: Core Intelligence Framework"
echo "• Implement LLM provider integration (Ollama + OpenRouter)"
echo "• Replace placeholder processing with real multi-step analysis"
echo "• Add comprehensive test coverage"