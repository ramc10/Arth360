#!/usr/bin/env python3
import sys
import traceback
import os

sys.path.insert(0, '/app')

try:
    from publisher import NewsletterPublisher

    print("Creating publisher...")
    pub = NewsletterPublisher()

    print("Getting unpublished editions...")
    editions = pub.get_unpublished_editions()

    if not editions:
        print("No editions found")
        sys.exit(1)

    edition = editions[0]
    print(f"Edition ID: {edition['id']}")

    # Test step by step
    print("\n[1] Fetching sections...")
    sections = pub.get_edition_sections(edition['id'])
    print(f"    Found {len(sections)} sections")

    print("\n[2] Formatting sections...")
    formatted_sections = []
    for section in sections:
        formatted_sections.append({
            'title': section['section_title'],
            'content': pub.format_content_paragraphs(section['section_content'])
        })
    print(f"    Formatted {len(formatted_sections)} sections")

    print("\n[3] Preparing template data...")
    from datetime import datetime
    template_data = {
        'title': edition['title'],
        'edition_number': edition['edition_number'],
        'publish_date': edition['publish_date'].strftime('%B %d, %Y'),
        'intro_text': edition['intro_text'],
        'sections': formatted_sections,
        'sections_count': len(sections),
        'articles_count': edition['articles_used'],
        'word_count': edition['word_count'],
        'generation_time': datetime.now().strftime('%B %d, %Y at %I:%M %p')
    }
    print("    Template data prepared")

    print("\n[4] Rendering template...")
    template = pub.jinja_env.get_template('newsletter.html')
    html_content = template.render(**template_data)
    print(f"    Template rendered ({len(html_content)} chars)")

    print("\n[5] Creating PDF path...")
    pdf_filename = f"AI_Newsletter_Edition_{edition['edition_number']}_{edition['publish_date'].strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(pub.pdf_dir, pdf_filename)
    print(f"    PDF path: {pdf_path}")

    print("\n[6] Generating PDF with WeasyPrint...")
    from weasyprint import HTML
    HTML(string=html_content).write_pdf(pdf_path)
    print("    PDF generated!")

    print(f"\n✓ SUCCESS: {pdf_filename}")

except Exception as e:
    print(f"\n✗ ERROR at current step: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
