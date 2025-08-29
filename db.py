import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, db_path="messages.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self._migrate_schema()
        logger.debug("Database initialized at %s", db_path)

    def _create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT,
                server_name TEXT,
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
                server_id TEXT,
                server_name TEXT,
                channel TEXT,
                last_fetched DATETIME,
                PRIMARY KEY (server_id, channel)
            )
        """
        )
        self.conn.commit()

    def _migrate_schema(self):
        """Migrate existing database schema to include server information."""
        cursor = self.conn.cursor()
        
        # Check if server_id column exists in messages table
        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'server_id' not in columns:
            logger.info("Migrating messages table to include server information")
            # Add server columns to messages table
            self.conn.execute("ALTER TABLE messages ADD COLUMN server_id TEXT")
            self.conn.execute("ALTER TABLE messages ADD COLUMN server_name TEXT")
            
            # Set default values for existing records (will be NULL for now)
            logger.info("Migration completed - existing messages will have NULL server_id until bot reconnects")
        
        # Check if we need to recreate channel_meta table with new schema
        cursor.execute("PRAGMA table_info(channel_meta)")
        channel_meta_columns = [column[1] for column in cursor.fetchall()]
        
        if 'server_id' not in channel_meta_columns:
            logger.info("Migrating channel_meta table to include server information")
            # Backup existing channel_meta data
            cursor.execute("SELECT channel, last_fetched FROM channel_meta")
            old_data = cursor.fetchall()
            
            # Drop and recreate channel_meta table with new schema
            self.conn.execute("DROP TABLE channel_meta")
            self.conn.execute(
                """
                CREATE TABLE channel_meta (
                    server_id TEXT,
                    server_name TEXT,
                    channel TEXT,
                    last_fetched DATETIME,
                    PRIMARY KEY (server_id, channel)
                )
            """
            )
            
            # Note: Old channel_meta data cannot be restored without server info
            # It will be rebuilt as the bot reconnects to channels
            logger.info("Channel metadata will be rebuilt as bot reconnects to servers")
            
        self.conn.commit()

    def add_message(self, author, content, channel, timestamp=None, server_id=None, server_name=None):
        timestamp = timestamp or datetime.now(timezone.utc)
        query = "INSERT INTO messages (server_id, server_name, channel, author, content, timestamp) VALUES (?, ?, ?, ?, ?, ?)"
        params = (str(server_id) if server_id else None, str(server_name) if server_name else None, 
                 str(channel), str(author), content, timestamp.isoformat())

        logger.debug("Executing query: %s | params=%s", query, params)
        self.conn.execute(query, params)
        self.conn.commit()

    def get_messages_since(self, since_datetime, channel=None, server_id=None):
        """Return a list of tuples (author, content) for messages since `since_datetime`.
        
        Args:
            since_datetime: Start datetime for message retrieval
            channel: Optional channel name to filter by. If None, returns all channels.
            server_id: Optional server ID to filter by. If None, returns all servers.
        """
        conditions = ["timestamp >= ?"]
        params = [since_datetime.isoformat()]
        
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
            
        if server_id:
            conditions.append("server_id = ?")
            params.append(str(server_id))
            
        query = f"SELECT author, content FROM messages WHERE {' AND '.join(conditions)} ORDER BY timestamp ASC"

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        filter_desc = []
        if channel:
            filter_desc.append(f"channel #{channel}")
        if server_id:
            filter_desc.append(f"server {server_id}")
        
        if filter_desc:
            logger.info("Fetched %d messages from %s since %s", len(results), " and ".join(filter_desc), since_datetime)
        else:
            logger.info("Fetched %d messages from all channels/servers since %s", len(results), since_datetime)

        return results

    def get_messages_in_range(self, start_datetime, end_datetime, channel=None, server_id=None):
        """Return a list of tuples (author, content) for messages in date range.
        
        Args:
            start_datetime: Start datetime for message retrieval
            end_datetime: End datetime for message retrieval  
            channel: Optional channel name to filter by. If None, returns all channels.
            server_id: Optional server ID to filter by. If None, returns all servers.
        """
        conditions = ["timestamp >= ?", "timestamp < ?"]
        params = [start_datetime.isoformat(), end_datetime.isoformat()]
        
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
            
        if server_id:
            conditions.append("server_id = ?")
            params.append(str(server_id))
            
        query = f"SELECT author, content FROM messages WHERE {' AND '.join(conditions)} ORDER BY timestamp ASC"

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        filter_desc = []
        if channel:
            filter_desc.append(f"channel #{channel}")
        if server_id:
            filter_desc.append(f"server {server_id}")
        
        if filter_desc:
            logger.info("Fetched %d messages from %s between %s and %s", len(results), " and ".join(filter_desc), start_datetime, end_datetime)
        else:
            logger.info("Fetched %d messages from all channels/servers between %s and %s", len(results), start_datetime, end_datetime)

        return results

    def get_last_fetched(self, channel, server_id):
        row = self.conn.execute(
            "SELECT last_fetched FROM channel_meta WHERE channel = ? AND server_id = ?", (channel, str(server_id))
        ).fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    def update_last_fetched(self, channel, timestamp, server_id, server_name=None):
        self.conn.execute(
            """
            INSERT INTO channel_meta(server_id, server_name, channel, last_fetched)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(server_id, channel) DO UPDATE SET 
                last_fetched=excluded.last_fetched,
                server_name=excluded.server_name
        """,
            (str(server_id), str(server_name) if server_name else None, channel, timestamp.isoformat()),
        )
        self.conn.commit()

    def get_active_channels(self, since_datetime, server_id=None):
        """Return list of channels that have messages since the given datetime.
        
        Args:
            since_datetime: Start datetime for channel activity check
            server_id: Optional server ID to filter by. If None, returns all servers.
        
        Returns:
            List of tuples (server_id, server_name, channel) or just (channel,) if server_id specified
        """
        if server_id:
            query = "SELECT DISTINCT channel FROM messages WHERE timestamp >= ? AND server_id = ? ORDER BY channel"
            params = (since_datetime.isoformat(), str(server_id))
        else:
            query = "SELECT DISTINCT server_id, server_name, channel FROM messages WHERE timestamp >= ? ORDER BY server_id, channel"
            params = (since_datetime.isoformat(),)
        
        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if server_id:
            results = [row[0] for row in results]  # Just channel names
            logger.info("Found %d active channels in server %s since %s", len(results), server_id, since_datetime)
        else:
            logger.info("Found %d active channels across all servers since %s", len(results), since_datetime)
        
        return results

    def get_active_channels_in_range(self, start_datetime, end_datetime, server_id=None):
        """Return list of channels that have messages in the given date range.
        
        Args:
            start_datetime: Start datetime for range
            end_datetime: End datetime for range
            server_id: Optional server ID to filter by. If None, returns all servers.
            
        Returns:
            List of tuples (server_id, server_name, channel) or just (channel,) if server_id specified
        """
        if server_id:
            query = "SELECT DISTINCT channel FROM messages WHERE timestamp >= ? AND timestamp < ? AND server_id = ? ORDER BY channel"
            params = (start_datetime.isoformat(), end_datetime.isoformat(), str(server_id))
        else:
            query = "SELECT DISTINCT server_id, server_name, channel FROM messages WHERE timestamp >= ? AND timestamp < ? ORDER BY server_id, channel"
            params = (start_datetime.isoformat(), end_datetime.isoformat())
        
        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if server_id:
            results = [row[0] for row in results]  # Just channel names
            logger.info("Found %d active channels in server %s between %s and %s", len(results), server_id, start_datetime, end_datetime)
        else:
            logger.info("Found %d active channels across all servers between %s and %s", len(results), start_datetime, end_datetime)
        
        return results

    def get_servers(self):
        """Return list of all servers with messages in database."""
        query = "SELECT DISTINCT server_id, server_name FROM messages WHERE server_id IS NOT NULL ORDER BY server_name"
        
        logger.debug("Executing query: %s", query)
        cursor = self.conn.execute(query)
        results = cursor.fetchall()
        
        logger.info("Found %d servers in database", len(results))
        return results
