#!/usr/bin/env python3
import sys
import traceback

sys.path.insert(0, '/app')

try:
    from publisher import NewsletterPublisher

    print("Creating publisher...")
    pub = NewsletterPublisher()

    print("Getting unpublished editions...")
    editions = pub.get_unpublished_editions()
    print(f"Found {len(editions)} unpublished editions")

    if editions:
        edition = editions[0]
        print(f"\nEdition details:")
        print(f"  ID: {edition['id']}")
        print(f"  Number: {edition['edition_number']}")
        print(f"  Title: {edition['title']}")

        print("\nGenerating PDF...")
        result = pub.generate_pdf(edition)

        if result:
            print(f"\n✓ SUCCESS!")
            print(f"  PDF: {result['filename']}")
            print(f"  Size: {result['size_kb']} KB")
        else:
            print("\n✗ PDF generation returned None")
    else:
        print("No unpublished editions found")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
