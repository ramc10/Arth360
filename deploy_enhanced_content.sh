#!/bin/bash

# Deploy Enhanced Content Extractor
# This script safely deploys the enhanced content extraction service

set -e

echo "======================================================================"
echo "ENHANCED CONTENT EXTRACTOR - DEPLOYMENT SCRIPT"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

if [ ! -f "content/content_v2.py" ]; then
    echo -e "${RED}Error: content/content_v2.py not found${NC}"
    exit 1
fi

echo "Step 1: Pre-deployment Checks"
echo "---------------------------------------------------------------------"

# Check current success rate
echo "Current extraction statistics:"
docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se "
SELECT
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    COUNT(fm.id) - COUNT(ac.id) as unprocessed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id;
" 2>/dev/null || echo "Could not fetch statistics"

echo ""
read -p "Continue with deployment? [y/N]: " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

echo ""
echo "Step 2: Backup Current Version"
echo "---------------------------------------------------------------------"

# Backup current content.py
if [ -f "content/content.py" ]; then
    BACKUP_FILE="content/content_backup_$(date +%Y%m%d_%H%M%S).py"
    cp content/content.py "$BACKUP_FILE"
    echo -e "${GREEN}✓${NC} Backed up content.py to $BACKUP_FILE"
else
    echo -e "${YELLOW}⚠${NC}  content.py not found, will create new file"
fi

echo ""
echo "Step 3: Stop Content Service"
echo "---------------------------------------------------------------------"
docker-compose stop content
echo -e "${GREEN}✓${NC} Content service stopped"

echo ""
echo "Step 4: Deploy Enhanced Version"
echo "---------------------------------------------------------------------"
cp content/content_v2.py content/content.py
echo -e "${GREEN}✓${NC} Deployed content_v2.py as content.py"

echo ""
echo "Step 5: Rebuild Content Service"
echo "---------------------------------------------------------------------"
docker-compose build content
echo -e "${GREEN}✓${NC} Content service rebuilt"

echo ""
echo "Step 6: Start Content Service"
echo "---------------------------------------------------------------------"
docker-compose up -d content
echo -e "${GREEN}✓${NC} Content service started"

echo ""
echo "Step 7: Verify Service Started"
echo "---------------------------------------------------------------------"
sleep 3
if docker-compose ps content | grep -q "Up"; then
    echo -e "${GREEN}✓${NC} Content service is running"
else
    echo -e "${RED}✗${NC} Content service failed to start!"
    echo "Check logs with: docker-compose logs content"
    exit 1
fi

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Monitor logs for 30 minutes:"
echo "   ${YELLOW}docker-compose logs -f content${NC}"
echo ""
echo "2. Check for improvements (look for):"
echo "   - ✓ Resolved Google News URL to: ..."
echo "   - ✓ Extracted XXXX chars from ..."
echo "   - Success Rate: XX.X% (should increase from 48.8%)"
echo ""
echo "3. After 2 hours, check statistics:"
echo "   ${YELLOW}docker exec arth360-mysql mysql -urss_user -p10_Leomessi -Drss_reader -se \"
SELECT
    COUNT(fm.id) as total,
    COUNT(ac.id) as processed,
    ROUND(COUNT(ac.id) / COUNT(fm.id) * 100, 2) as success_rate
FROM feed_metadata fm
LEFT JOIN article_content ac ON fm.id = ac.url_id;
\"${NC}"
echo ""
echo "4. Reprocess failed articles (after 2-4 hours):"
echo "   ${YELLOW}python3 scripts/reprocess_failed_articles.py --limit 100 --dry-run${NC}"
echo "   ${YELLOW}python3 scripts/reprocess_failed_articles.py --limit 1000${NC}"
echo ""
echo "5. If issues occur, rollback with:"
echo "   ${YELLOW}docker-compose stop content${NC}"
echo "   ${YELLOW}cp $BACKUP_FILE content/content.py${NC}"
echo "   ${YELLOW}docker-compose build content && docker-compose up -d content${NC}"
echo ""
echo "======================================================================"
echo ""
echo "Showing live logs (Ctrl+C to exit):"
echo ""

# Show logs
docker-compose logs -f content
