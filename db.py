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
                server_id TEXT,
                server_name TEXT,
                channel_id TEXT,
                channel_name TEXT,
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
                channel_id TEXT,
                channel_name TEXT,
                category_id TEXT,
                category_name TEXT,
                last_fetched DATETIME,
                PRIMARY KEY (server_id, channel_id)
            )
        """
        )
        self.conn.commit()

    def add_message(
        self,
        author,
        content,
        channel_name,
        timestamp=None,
        server_id=None,
        server_name=None,
        channel_id=None,
    ):
        timestamp = timestamp or datetime.now(timezone.utc)
        query = "INSERT INTO messages (server_id, server_name, channel_id, channel_name, author, content, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)"
        params = (
            str(server_id) if server_id else None,
            str(server_name) if server_name else None,
            str(channel_id) if channel_id else None,
            str(channel_name),
            str(author),
            content,
            timestamp.isoformat(),
        )

        logger.debug("Executing query: %s | params=%s", query, params)
        self.conn.execute(query, params)
        self.conn.commit()

    def get_messages_since(
        self, since_datetime, channel_name=None, server_id=None, channel_id=None
    ):
        """Return a list of tuples (author, content) for messages since `since_datetime`.

        Args:
            since_datetime: Start datetime for message retrieval
            channel_name: Optional channel name to filter by. If None, returns all channels.
            server_id: Optional server ID to filter by. If None, returns all servers.
            channel_id: Optional channel ID to filter by (more precise than channel_name).
        """
        conditions = ["timestamp >= ?"]
        params = [since_datetime.isoformat()]

        # Prefer channel_id over channel_name for precision
        if channel_id:
            conditions.append("channel_id = ?")
            params.append(str(channel_id))
        elif channel_name:
            conditions.append("channel_name = ?")
            params.append(channel_name)

        if server_id:
            conditions.append("server_id = ?")
            params.append(str(server_id))

        query = f"SELECT author, content FROM messages WHERE {' AND '.join(conditions)} ORDER BY timestamp ASC"

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()

        filter_desc = []
        if channel_id:
            filter_desc.append(f"channel_id {channel_id}")
        elif channel_name:
            filter_desc.append(f"channel #{channel_name}")
        if server_id:
            filter_desc.append(f"server {server_id}")

        if filter_desc:
            logger.info(
                "Fetched %d messages from %s since %s",
                len(results),
                " and ".join(filter_desc),
                since_datetime,
            )
        else:
            logger.info(
                "Fetched %d messages from all channels/servers since %s",
                len(results),
                since_datetime,
            )

        return results

    def get_messages_in_range(
        self,
        start_datetime,
        end_datetime,
        channel_name=None,
        server_id=None,
        channel_id=None,
    ):
        """Return a list of tuples (author, content) for messages in date range.

        Args:
            start_datetime: Start datetime for message retrieval
            end_datetime: End datetime for message retrieval
            channel_name: Optional channel name to filter by. If None, returns all channels.
            server_id: Optional server ID to filter by. If None, returns all servers.
            channel_id: Optional channel ID to filter by (more precise than channel_name).
        """
        conditions = ["timestamp >= ?", "timestamp < ?"]
        params = [start_datetime.isoformat(), end_datetime.isoformat()]

        # Prefer channel_id over channel_name for precision
        if channel_id:
            conditions.append("channel_id = ?")
            params.append(str(channel_id))
        elif channel_name:
            conditions.append("channel_name = ?")
            params.append(channel_name)

        if server_id:
            conditions.append("server_id = ?")
            params.append(str(server_id))

        query = f"SELECT author, content FROM messages WHERE {' AND '.join(conditions)} ORDER BY timestamp ASC"

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()

        filter_desc = []
        if channel_id:
            filter_desc.append(f"channel_id {channel_id}")
        elif channel_name:
            filter_desc.append(f"channel #{channel_name}")
        if server_id:
            filter_desc.append(f"server {server_id}")

        if filter_desc:
            logger.info(
                "Fetched %d messages from %s between %s and %s",
                len(results),
                " and ".join(filter_desc),
                start_datetime,
                end_datetime,
            )
        else:
            logger.info(
                "Fetched %d messages from all channels/servers between %s and %s",
                len(results),
                start_datetime,
                end_datetime,
            )

        return results

    def get_last_fetched(self, channel_id, server_id, channel_name=None):
        # Try channel_id first (most precise)
        row = self.conn.execute(
            "SELECT last_fetched FROM channel_meta WHERE channel_id = ? AND server_id = ?",
            (str(channel_id), str(server_id)),
        ).fetchone()

        # Fallback to channel_name if channel_id not found (for backward compatibility)
        if not row and channel_name:
            row = self.conn.execute(
                "SELECT last_fetched FROM channel_meta WHERE channel_name = ? AND server_id = ?",
                (channel_name, str(server_id)),
            ).fetchone()

        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    def update_last_fetched(
        self,
        channel_id,
        timestamp,
        server_id,
        server_name=None,
        channel_name=None,
        category_id=None,
        category_name=None,
    ):
        self.conn.execute(
            """
            INSERT INTO channel_meta(server_id, server_name, channel_id, channel_name, category_id, category_name, last_fetched)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(server_id, channel_id) DO UPDATE SET 
                last_fetched=excluded.last_fetched,
                server_name=excluded.server_name,
                channel_name=excluded.channel_name,
                category_id=excluded.category_id,
                category_name=excluded.category_name
        """,
            (
                str(server_id),
                str(server_name) if server_name else None,
                str(channel_id),
                str(channel_name) if channel_name else None,
                str(category_id) if category_id else None,
                str(category_name) if category_name else None,
                timestamp.isoformat(),
            ),
        )
        self.conn.commit()

    def get_active_channels(self, since_datetime, server_id=None):
        """Return list of channels that have messages since the given datetime.

        Args:
            since_datetime: Start datetime for channel activity check
            server_id: Optional server ID to filter by. If None, returns all servers.

        Returns:
            List of tuples (server_id, server_name, channel_id, channel_name) or just (channel_name,) if server_id specified
        """
        if server_id:
            query = "SELECT DISTINCT channel_name FROM messages WHERE timestamp >= ? AND server_id = ? ORDER BY channel_name"
            params = (since_datetime.isoformat(), str(server_id))
        else:
            query = "SELECT DISTINCT server_id, server_name, channel_id, channel_name FROM messages WHERE timestamp >= ? ORDER BY server_id, channel_name"
            params = (since_datetime.isoformat(),)

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()

        if server_id:
            results = [row[0] for row in results]  # Just channel names
            logger.info(
                "Found %d active channels in server %s since %s",
                len(results),
                server_id,
                since_datetime,
            )
        else:
            logger.info(
                "Found %d active channels across all servers since %s",
                len(results),
                since_datetime,
            )

        return results

    def get_active_channels_in_range(
        self, start_datetime, end_datetime, server_id=None
    ):
        """Return list of channels that have messages in the given date range.

        Args:
            start_datetime: Start datetime for range
            end_datetime: End datetime for range
            server_id: Optional server ID to filter by. If None, returns all servers.

        Returns:
            List of tuples (server_id, server_name, channel_id, channel_name) or just (channel_name,) if server_id specified
        """
        if server_id:
            query = "SELECT DISTINCT channel_name FROM messages WHERE timestamp >= ? AND timestamp < ? AND server_id = ? ORDER BY channel_name"
            params = (
                start_datetime.isoformat(),
                end_datetime.isoformat(),
                str(server_id),
            )
        else:
            query = "SELECT DISTINCT server_id, server_name, channel_id, channel_name FROM messages WHERE timestamp >= ? AND timestamp < ? ORDER BY server_id, channel_name"
            params = (start_datetime.isoformat(), end_datetime.isoformat())

        logger.debug("Executing query: %s | params=%s", query, params)
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()

        if server_id:
            results = [row[0] for row in results]  # Just channel names
            logger.info(
                "Found %d active channels in server %s between %s and %s",
                len(results),
                server_id,
                start_datetime,
                end_datetime,
            )
        else:
            logger.info(
                "Found %d active channels across all servers between %s and %s",
                len(results),
                start_datetime,
                end_datetime,
            )

        return results

    def get_servers(self):
        """Return list of all servers with messages in database."""
        query = "SELECT DISTINCT server_id, server_name FROM messages WHERE server_id IS NOT NULL ORDER BY server_name"

        logger.debug("Executing query: %s", query)
        cursor = self.conn.execute(query)
        results = cursor.fetchall()

        logger.info("Found %d servers in database", len(results))
        return results

    def get_channel_category(self, channel_id=None, channel_name=None, server_id=None):
        """Get category information for a specific channel.

        Args:
            channel_id: Channel ID (preferred)
            channel_name: Channel name (fallback)
            server_id: Server ID for disambiguation

        Returns:
            Tuple of (category_id, category_name) or (None, None) if no category found
        """
        if channel_id and server_id:
            # Preferred: lookup by channel_id and server_id
            row = self.conn.execute(
                "SELECT category_id, category_name FROM channel_meta WHERE channel_id = ? AND server_id = ?",
                (str(channel_id), str(server_id)),
            ).fetchone()
        elif channel_name and server_id:
            # Fallback: lookup by channel_name and server_id
            row = self.conn.execute(
                "SELECT category_id, category_name FROM channel_meta WHERE channel_name = ? AND server_id = ?",
                (channel_name, str(server_id)),
            ).fetchone()
        else:
            return (None, None)

        if row:
            return (row[0], row[1])
        else:
            return (None, None)
