import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Establish a connection to the MySQL database"""
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")

    def create_tables(self):
        """Create necessary tables if they don't exist"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS news_feeds (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            link VARCHAR(512) NOT NULL,
            published DATETIME NOT NULL,
            source VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_news (link, source)
        )
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(create_table_query)
            self.connection.commit()
            print("News feeds table created/verified")
        except Error as e:
            print(f"Error creating tables: {e}")

    def insert_news_item(self, item):
        """Insert a news item into the database"""
        query = """
        INSERT IGNORE INTO news_feeds 
        (title, description, link, published, source) 
        VALUES (%s, %s, %s, %s, %s)
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (
                item['title'],
                item['description'],
                item['link'],
                item['published'],
                item['source']
            ))
            self.connection.commit()
            if cursor.rowcount > 0:
                print(f"Inserted: {item['title'][:50]}...")
            else:
                print(f"Skipped duplicate: {item['title'][:50]}...")
        except Error as e:
            print(f"Error inserting news item: {e}")

    def close(self):
        """Close the database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed")
