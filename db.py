import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, db_path="messages.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        logger.debug("Database initialized at %s", db_path)

    def _create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                author TEXT,
                content TEXT,
                timestamp DATETIME
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_meta (
                channel TEXT PRIMARY KEY,
                last_fetched DATETIME
            )
        """
        )
        self.conn.commit()

    def add_message(self, author, content, channel, timestamp=None):
        timestamp = timestamp or datetime.now(timezone.utc)
        query = "INSERT INTO messages (channel, author, content, timestamp) VALUES (?, ?, ?, ?)"
        params = (str(channel), str(author), content, timestamp.isoformat())

        logger.debug("Executing query: %s | params=%s", query, params)
        self.conn.execute(query, params)
        self.conn.commit()

    def get_messages_since(self, since_datetime, channel=None):
        """Return a list of tuples (author, content) for messages since `since_datetime`.
        
        Args:
            since_datetime: Start datetime for message retrieval
            channel: Optional channel name to filter by. If None, returns all channels.
        """
        if channel:
            query = "SELECT author, content FROM messages WHERE timestamp >= ? AND channel = ? ORDER BY timestamp ASC"
            params = (since_datetime.isoformat(), channel)
        else:
            query = "SELECT author, content FROM messages WHERE timestamp >= ? ORDER BY timestamp ASC"
            params = (since_datetime.isoformat(),)

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if channel:
            logger.info("Fetched %d messages from #%s since %s", len(results), channel, since_datetime)
        else:
            logger.info("Fetched %d messages from all channels since %s", len(results), since_datetime)

        return results

    def get_messages_in_range(self, start_datetime, end_datetime, channel=None):
        """Return a list of tuples (author, content) for messages in date range.
        
        Args:
            start_datetime: Start datetime for message retrieval
            end_datetime: End datetime for message retrieval  
            channel: Optional channel name to filter by. If None, returns all channels.
        """
        if channel:
            query = "SELECT author, content FROM messages WHERE timestamp >= ? AND timestamp < ? AND channel = ? ORDER BY timestamp ASC"
            params = (start_datetime.isoformat(), end_datetime.isoformat(), channel)
        else:
            query = "SELECT author, content FROM messages WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC"
            params = (start_datetime.isoformat(), end_datetime.isoformat())

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if channel:
            logger.info("Fetched %d messages from #%s between %s and %s", len(results), channel, start_datetime, end_datetime)
        else:
            logger.info("Fetched %d messages from all channels between %s and %s", len(results), start_datetime, end_datetime)

        return results

    def get_last_fetched(self, channel):
        row = self.conn.execute(
            "SELECT last_fetched FROM channel_meta WHERE channel = ?", (channel,)
        ).fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    def update_last_fetched(self, channel, timestamp):
        self.conn.execute(
            """
            INSERT INTO channel_meta(channel, last_fetched)
            VALUES (?, ?)
            ON CONFLICT(channel) DO UPDATE SET last_fetched=excluded.last_fetched
        """,
            (channel, timestamp.isoformat()),
        )
        self.conn.commit()

    def get_active_channels(self, since_datetime):
        """Return list of channels that have messages since the given datetime."""
        query = "SELECT DISTINCT channel FROM messages WHERE timestamp >= ? ORDER BY channel"
        params = (since_datetime.isoformat(),)
        
        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = [row[0] for row in cursor.fetchall()]
        
        logger.info("Found %d active channels since %s", len(results), since_datetime)
        return results

    def get_active_channels_in_range(self, start_datetime, end_datetime):
        """Return list of channels that have messages in the given date range."""
        query = "SELECT DISTINCT channel FROM messages WHERE timestamp >= ? AND timestamp < ? ORDER BY channel"
        params = (start_datetime.isoformat(), end_datetime.isoformat())
        
        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = [row[0] for row in cursor.fetchall()]
        
        logger.info("Found %d active channels between %s and %s", len(results), start_datetime, end_datetime)
        return results
