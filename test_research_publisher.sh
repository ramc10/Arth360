#!/bin/bash

# Test script for Research Brief Publisher
# This script helps test the research brief publishing functionality

set -e

echo "========================================"
echo "Research Brief Publisher Test Script"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Step 1: Checking Docker services..."
if docker-compose ps | grep -q "arth360-mysql.*Up"; then
    echo -e "${GREEN}✓${NC} MySQL is running"
else
    echo -e "${RED}✗${NC} MySQL is not running"
    echo "  Run: docker-compose up -d mysql"
    exit 1
fi

echo ""
echo "Step 2: Checking for research briefs in database..."
BRIEF_COUNT=$(docker exec arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} -D${DB_NAME} -se \
    "SELECT COUNT(*) FROM research_briefs WHERE articles_analyzed > 0;" 2>/dev/null || echo "0")

if [ "$BRIEF_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $BRIEF_COUNT research brief(s)"
else
    echo -e "${YELLOW}!${NC} No research briefs found"
    echo "  The research service needs to generate briefs first"
    echo "  Checking if user watchlist exists..."

    WATCHLIST_COUNT=$(docker exec arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} -D${DB_NAME} -se \
        "SELECT COUNT(*) FROM user_watchlist;" 2>/dev/null || echo "0")

    if [ "$WATCHLIST_COUNT" -eq 0 ]; then
        echo -e "${RED}✗${NC} No companies in watchlist"
        echo ""
        echo "  To add companies to watchlist, run:"
        echo "  docker exec -it arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME}"
        echo ""
        echo "  Then execute:"
        echo "  INSERT INTO users (email) VALUES ('test@example.com');"
        echo "  INSERT INTO user_watchlist (user_id, company_symbol, company_name) VALUES"
        echo "    (1, 'AAPL', 'Apple Inc'),"
        echo "    (1, 'TSLA', 'Tesla Inc'),"
        echo "    (1, 'NVDA', 'NVIDIA Corporation');"
        exit 1
    else
        echo -e "${GREEN}✓${NC} Found $WATCHLIST_COUNT companies in watchlist"
        echo "  Wait for research service to generate briefs (runs hourly)"
    fi
fi

echo ""
echo "Step 3: Checking for unpublished briefs..."
UNPUBLISHED=$(docker exec arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} -D${DB_NAME} -se \
    "SELECT COUNT(*) FROM research_briefs rb
     LEFT JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
     WHERE rbp.brief_id IS NULL AND rb.articles_analyzed > 0;" 2>/dev/null || echo "0")

if [ "$UNPUBLISHED" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $UNPUBLISHED unpublished brief(s)"

    echo ""
    echo "Companies ready to publish:"
    docker exec arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} -D${DB_NAME} -se \
        "SELECT CONCAT('  - ', company_symbol, ' (', DATE_FORMAT(brief_date, '%Y-%m-%d'), ', ', articles_analyzed, ' articles)')
         FROM research_briefs rb
         LEFT JOIN research_briefs_published rbp ON rb.id = rbp.brief_id
         WHERE rbp.brief_id IS NULL AND rb.articles_analyzed > 0
         ORDER BY generated_at DESC;" 2>/dev/null
else
    echo -e "${YELLOW}!${NC} All briefs have been published"
    echo ""
    echo "  To test re-publishing, you can clear the published table:"
    echo "  docker exec -it arth360-mysql mysql -u${DB_USER} -p${DB_PASSWORD} -D${DB_NAME} -e 'TRUNCATE TABLE research_briefs_published;'"
fi

echo ""
echo "Step 4: Checking Telegram configuration..."
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}✗${NC} TELEGRAM_BOT_TOKEN not set in .env"
    exit 1
else
    echo -e "${GREEN}✓${NC} Telegram bot token configured"
fi

if [ -z "$TELEGRAM_CHANNEL_ID" ]; then
    echo -e "${RED}✗${NC} TELEGRAM_CHANNEL_ID not set in .env"
    exit 1
else
    echo -e "${GREEN}✓${NC} Telegram channel ID configured: $TELEGRAM_CHANNEL_ID"
fi

echo ""
echo "Step 5: Testing Telegram bot connection..."
BOT_RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe")
if echo "$BOT_RESPONSE" | grep -q '"ok":true'; then
    BOT_NAME=$(echo "$BOT_RESPONSE" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✓${NC} Bot connection successful (@${BOT_NAME})"
else
    echo -e "${RED}✗${NC} Bot connection failed"
    echo "  Response: $BOT_RESPONSE"
    exit 1
fi

echo ""
echo "========================================"
echo "Ready to Build and Test!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Build the research publisher service:"
echo "   ${YELLOW}docker-compose build research-publisher${NC}"
echo ""
echo "2. Start the service:"
echo "   ${YELLOW}docker-compose up -d research-publisher${NC}"
echo ""
echo "3. Watch the logs:"
echo "   ${YELLOW}docker-compose logs -f research-publisher${NC}"
echo ""
echo "4. Or test manually (one-time run):"
echo "   ${YELLOW}docker-compose run --rm research-publisher python research_telegram_publisher.py${NC}"
echo "   (Press Ctrl+C after first cycle completes)"
echo ""

if [ "$UNPUBLISHED" -gt 0 ]; then
    echo -e "${GREEN}You have $UNPUBLISHED brief(s) ready to publish!${NC}"
else
    echo -e "${YELLOW}No unpublished briefs available. Wait for research service to generate them.${NC}"
fi

echo ""
