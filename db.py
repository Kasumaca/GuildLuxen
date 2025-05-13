import psycopg2, os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def create_room(room_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO rooms (name) VALUES (%s) ON CONFLICT DO NOTHING", (room_name,))
            conn.commit()

def room_exists(room_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rooms WHERE name = %s", (room_name,))
            row = cur.fetchone()
            return row[0] if row else None

def list_rooms():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.name, COUNT(rc.id)
                FROM rooms r
                LEFT JOIN room_channels rc ON rc.room_id = r.id
                GROUP BY r.id
                ORDER BY r.name
            """)
            return cur.fetchall()

def add_channel_to_room(room_name, channel_id, webhook_url):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rooms WHERE name = %s", (room_name,))
            room = cur.fetchone()
            if not room:
                raise ValueError("Room not found")
            room_id = room[0]

            cur.execute("""
                INSERT INTO room_channels (room_id, channel_id, webhook_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (room_id, channel_id) DO UPDATE
                SET webhook_url = EXCLUDED.webhook_url
            """, (room_id, channel_id, webhook_url))
            conn.commit()

def get_connected_webhooks(channel_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # First, get the room ID that this channel belongs to
            cur.execute("""
                SELECT room_id
                FROM room_channels
                WHERE channel_id = %s
            """, (str(channel_id),))
            room = cur.fetchone()

            if not room:
                return []  # <- Return empty list instead of None

            room_id = room[0]

            # Now fetch all other channels in the same room
            cur.execute("""
                SELECT channel_id, webhook_url
                FROM room_channels
                WHERE room_id = %s AND channel_id != %s
            """, (room_id, str(channel_id)))
            results = cur.fetchall()
            return results or []  # <- Also ensure this isn't None
