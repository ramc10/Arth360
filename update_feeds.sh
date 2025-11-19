#!/bin/bash

# Update RSS Feeds Configuration
# Replaces Google News feeds with direct publisher feeds

set -e

echo "======================================================================"
echo "RSS FEEDS UPDATE - Replace Google News with Direct Feeds"
echo "======================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backup current config
echo "Step 1: Backup current configuration"
echo "----------------------------------------------------------------------"
cp feeder/config.json feeder/config_backup_$(date +%Y%m%d_%H%M%S).json
echo -e "${GREEN}✓${NC} Backed up config.json"

# Show current feed count
CURRENT_COUNT=$(grep -c '"name":' feeder/config.json || echo "0")
NEW_COUNT=$(grep -c '"name":' feeder/config_new.json || echo "0")

echo ""
echo "Current feeds: $CURRENT_COUNT"
echo "New feeds: $NEW_COUNT"
echo ""

# Show what will change
echo "Changes:"
echo "----------------------------------------------------------------------"
echo -e "${RED}REMOVING:${NC}"
echo "  - All Google News feeds (~25 feeds with redirect URLs)"
echo ""
echo -e "${GREEN}ADDING:${NC}"
echo "  - Reuters (2 feeds)"
echo "  - TechCrunch, The Verge, Ars Technica, Wired"
echo "  - CNBC (3 feeds)"
echo "  - MarketWatch (2 feeds)"
echo "  - Yahoo Finance, ZDNet, Benzinga"
echo "  - Barron's, Motley Fool, IBD, Seeking Alpha"
echo "  - Economic Times, Financial Express (India)"
echo "  - Hindu Business Line (India)"
echo "  - CoinDesk, CoinTelegraph (Crypto)"
echo "  - Hacker News"
echo ""
echo -e "${YELLOW}KEEPING:${NC}"
echo "  - All Moneycontrol feeds"
echo "  - All Mint feeds"
echo "  - Business Today"
echo ""

read -p "Continue with feed update? [y/N]: " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Update cancelled."
    exit 1
fi

echo ""
echo "Step 2: Deploy new configuration"
echo "----------------------------------------------------------------------"
cp feeder/config_new.json feeder/config.json
echo -e "${GREEN}✓${NC} Deployed new config.json"

echo ""
echo "Step 3: Restart feeder service"
echo "----------------------------------------------------------------------"
docker-compose restart feeder
echo -e "${GREEN}✓${NC} Feeder service restarted"

echo ""
echo "Step 4: Monitor new feeds"
echo "----------------------------------------------------------------------"
echo "Watching for new articles from direct feeds..."
sleep 5

docker-compose logs feeder --tail 20 | grep -E "Stored|Failed|articles" || echo "Service starting..."

echo ""
echo "======================================================================"
echo "FEEDS UPDATE COMPLETE"
echo "======================================================================"
echo ""
echo "What changed:"
echo "  ✓ Replaced Google News feeds with 40+ direct publisher feeds"
echo "  ✓ No more redirect URLs - all direct article links"
echo "  ✓ Better quality sources with full content"
echo ""
echo "Expected improvements:"
echo "  - Much higher success rate (70-85%)"
echo "  - Faster article extraction"
echo "  - Better content quality"
echo ""
echo "Monitor feeds:"
echo "  ${YELLOW}docker-compose logs -f feeder${NC}"
echo ""
echo "Check new articles:"
echo "  ${YELLOW}docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se \"
SELECT source, COUNT(*) as count
FROM feed_metadata
WHERE published_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)
GROUP BY source
ORDER BY count DESC;
\"${NC}"
echo ""
echo "To rollback if needed:"
echo "  ${YELLOW}cp feeder/config_backup_*.json feeder/config.json${NC}"
echo "  ${YELLOW}docker-compose restart feeder${NC}"
echo ""
