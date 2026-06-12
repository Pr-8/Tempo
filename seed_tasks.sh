#!/bin/bash

# Tempo Task Seeder
# This script injects a set of test tasks into the Tempo API.

API_URL="http://localhost:8000/api/tasks/"

echo "🌱 Seeding test tasks..."

# 1. High Priority Flexible Task
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Study Linear Algebra",
    "course": "Math 201",
    "estimated_hours": 3.0,
    "deadline": "2026-06-06T23:59:59",
    "priority": 5,
    "is_fixed": false
  }' > /dev/null
echo "✅ Added: Study Linear Algebra (High Priority)"

# 2. Medium Priority Flexible Task
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Biology Lab Report",
    "course": "Bio 101",
    "estimated_hours": 5.0,
    "deadline": "2026-06-08T23:59:59",
    "priority": 3,
    "is_fixed": false
  }' > /dev/null
echo "✅ Added: Biology Lab Report (Medium Priority)"

# 3. Fixed Time Event (Today)
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Weekly Team Sync",
    "course": "General",
    "fixed_start": "2026-06-04T15:00:00",
    "fixed_end": "2026-06-04T16:00:00",
    "priority": 3,
    "is_fixed": true,
    "estimated_hours": 1.0,
    "deadline": "2026-06-04T23:59:59"
  }' > /dev/null
echo "✅ Added: Weekly Team Sync (Fixed Event)"

# 4. Low Priority Flexible Task
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Read History Chapter 4",
    "course": "History 101",
    "estimated_hours": 2.0,
    "deadline": "2026-06-11T23:59:59",
    "priority": 1,
    "is_fixed": false
  }' > /dev/null
echo "✅ Added: Read History Chapter 4 (Low Priority)"

echo -e "\n✨ Seeding complete! Check your calendar for June 4-8, 2026."
