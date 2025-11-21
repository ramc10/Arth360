import os
import sys
import logging
import time
import json
import mysql.connector
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import pytz
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader

# Load environment variables
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))


class NewsletterPublisher:
    """Publishes AI newsletter as PDF"""

    def __init__(self):
        self.setup_logger()

        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME', 'rss_reader')
        }

        # Setup PDF output directory
        self.pdf_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'output'
        )
        os.makedirs(self.pdf_dir, exist_ok=True)

        # Setup Jinja2 template environment
        template_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'templates'
        )
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    def setup_logger(self):
        """Setup logger with date-based file rotation"""
        self.logger = logging.getLogger('NewsletterPublisher')
        self.logger.setLevel(logging.INFO)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # File handler
        file_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'publisher.log'),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console_handler)

    def get_db_connection(self):
        """Create database connection"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def get_unpublished_editions(self):
        """Fetch newsletter editions ready for publishing"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)

            query = """
                SELECT
                    ne.id,
                    ne.edition_number,
                    ne.publish_date,
                    ne.title,
                    ne.intro_text,
                    ne.content_json,
                    ne.word_count,
                    ne.articles_used,
                    ne.generated_at
                FROM newsletter_editions ne
                LEFT JOIN newsletter_published np ON ne.id = np.edition_id
                WHERE np.edition_id IS NULL
                    AND ne.status = 'ready'
                    AND ne.publish_date <= CURDATE()
                ORDER BY ne.publish_date ASC
                LIMIT 5
            """

            cursor.execute(query)
            editions = cursor.fetchall()
            cursor.close()

            return editions

        except Exception as e:
            self.logger.error(f"Failed to fetch unpublished editions: {e}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def get_edition_sections(self, edition_id):
        """Fetch sections for a newsletter edition"""
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)

            query = """
                SELECT
                    section_number,
                    section_title,
                    section_content,
                    value_chain_area,
                    word_count
                FROM newsletter_sections
                WHERE edition_id = %s
                ORDER BY section_number ASC
            """

            cursor.execute(query, (edition_id,))
            sections = cursor.fetchall()
            cursor.close()

            return sections

        except Exception as e:
            self.logger.error(f"Failed to fetch sections: {e}")
            return []
        finally:
            if conn.is_connected():
                conn.close()

    def format_content_paragraphs(self, content):
        """Format content into HTML paragraphs"""
        if not content:
            return ""

        # Split by double newlines for paragraphs
        paragraphs = content.split('\n\n')

        # Wrap each paragraph in <p> tags
        formatted = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # Handle single newlines within paragraphs
                para = para.replace('\n', ' ')
                formatted.append(f"<p>{para}</p>")

        return '\n'.join(formatted)

    def generate_pdf(self, edition):
        """Generate PDF from newsletter edition"""
        self.logger.info(f"Generating PDF for Edition #{edition['edition_number']}...")

        try:
            # Fetch sections
            sections = self.get_edition_sections(edition['id'])

            if not sections:
                self.logger.error("No sections found for this edition")
                return None

            # Format sections for template
            formatted_sections = []
            for section in sections:
                formatted_sections.append({
                    'title': section['section_title'],
                    'content': self.format_content_paragraphs(section['section_content'])
                })

            # Prepare template data
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

            # Render HTML template
            template = self.jinja_env.get_template('newsletter.html')
            html_content = template.render(**template_data)

            # Generate PDF filename
            pdf_filename = (
                f"AI_Newsletter_Edition_{edition['edition_number']}_"
                f"{edition['publish_date'].strftime('%Y%m%d')}.pdf"
            )
            pdf_path = os.path.join(self.pdf_dir, pdf_filename)

            # Generate PDF
            HTML(string=html_content).write_pdf(pdf_path)

            # Get file size
            pdf_size_kb = os.path.getsize(pdf_path) // 1024

            self.logger.info(f"✓ PDF generated: {pdf_filename} ({pdf_size_kb} KB)")

            return {
                'path': pdf_path,
                'filename': pdf_filename,
                'size_kb': pdf_size_kb
            }

        except Exception as e:
            import traceback
            self.logger.error(f"PDF generation failed: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def mark_as_published(self, edition_id, pdf_info):
        """Mark newsletter edition as published"""
        conn = self.get_db_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO newsletter_published
                (edition_id, pdf_path, pdf_size_kb, published_at, distribution_method, distribution_status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                edition_id,
                pdf_info['path'],
                pdf_info['size_kb'],
                datetime.now(),
                'local_pdf',
                'success'
            ))

            conn.commit()
            cursor.close()

            self.logger.info(f"✓ Marked edition {edition_id} as published")
            return True

        except Exception as e:
            self.logger.error(f"Failed to mark as published: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def publish_editions(self):
        """Publish all unpublished editions"""
        editions = self.get_unpublished_editions()

        if not editions:
            self.logger.info("No editions ready for publishing")
            return 0

        published_count = 0

        for edition in editions:
            self.logger.info(f"\nPublishing Edition #{edition['edition_number']}")

            # Generate PDF
            pdf_info = self.generate_pdf(edition)

            if pdf_info:
                # Mark as published
                if self.mark_as_published(edition['id'], pdf_info):
                    published_count += 1
                    self.logger.info(f"✓ Successfully published Edition #{edition['edition_number']}")
                    self.logger.info(f"  PDF: {pdf_info['filename']}")
                else:
                    self.logger.error(f"✗ Failed to mark as published")
            else:
                self.logger.error(f"✗ PDF generation failed for Edition #{edition['edition_number']}")

            # Rate limiting (if needed)
            time.sleep(1)

        return published_count

    def run(self):
        """Run publisher with IST scheduling"""
        self.logger.info("=" * 60)
        self.logger.info("NEWSLETTER PUBLISHER STARTING")
        self.logger.info("=" * 60)
        self.logger.info("Schedule: Monday & Thursday at 8:00 AM IST")
        self.logger.info(f"PDF output: {self.pdf_dir}")
        self.logger.info(f"Database: {self.db_config['host']}/{self.db_config['database']}")
        self.logger.info("=" * 60)

        try:
            while True:
                ist = pytz.timezone('Asia/Kolkata')
                now_ist = datetime.now(ist)

                # Check if it's publish time
                weekday = now_ist.weekday()
                hour = now_ist.hour
                minute = now_ist.minute

                # Monday (0) and Thursday (3) at 8:00 AM IST
                should_publish = (
                    (weekday == 0 or weekday == 3) and
                    hour == 8 and
                    minute == 0
                )

                if should_publish:
                    self.logger.info("\n" + "=" * 60)
                    self.logger.info(f"PUBLISH TIME: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
                    self.logger.info("=" * 60)

                    # Publish editions
                    count = self.publish_editions()

                    if count > 0:
                        self.logger.info(f"\n✓ Published {count} edition(s)")
                    else:
                        self.logger.info("\nNo editions to publish")

                    # Sleep for 2 hours to avoid duplicate publishing
                    self.logger.info("Sleeping for 2 hours...")
                    time.sleep(7200)
                else:
                    # Check every 30 minutes
                    self.logger.info(
                        f"Current time: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')} "
                        f"| Next check in 30 minutes"
                    )
                    time.sleep(1800)

        except KeyboardInterrupt:
            self.logger.info("\n\nShutting down Newsletter Publisher...")
        except Exception as e:
            self.logger.error(f"\nFatal error: {e}")
            self.logger.info("Retrying in 5 minutes...")
            time.sleep(300)


if __name__ == "__main__":
    publisher = NewsletterPublisher()
    publisher.run()
