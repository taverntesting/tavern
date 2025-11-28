"""Simple GraphQL test server for integration testing using SQLite and strawberry-graphql with subscriptions

Supports FastAPI ASGI for WebSocket subscriptions.
"""

import asyncio
import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import apsw
import strawberry
import uvicorn
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter


@strawberry.type
class User:
    id: strawberry.ID
    name: str
    email: str


@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    content: str
    author_id: strawberry.ID


db_conn: apsw.Connection
subscribers_lock = threading.Lock()
# A mapping of user IDs to queues
subscribers: dict = {}
pending_notifications = asyncio.Queue()


def update_hook(operation: str, database: str, table: bytes, rowid: int):
    if table == b"users":
        pending_notifications.put_nowait((table.decode(), rowid))


async def consumer_loop():
    while True:
        try:
            table, rowid = await pending_notifications.get()

            if table != "users":
                continue

            cur = db_conn.execute(
                "SELECT id, name, email FROM users WHERE rowid=?", (rowid,)
            )
            row = cur.fetchone()
            if row:
                user_dict = {
                    "id": strawberry.ID(str(row[0])),
                    "name": row[1],
                    "email": row[2],
                }
                user_obj = User(**user_dict)
                user_id = str(row[0])
                with subscribers_lock:
                    if user_id in subscribers:
                        for q in subscribers[user_id]:
                            await q.put(user_obj)
        except Exception as e:
            logging.error(f"Consumer error: {e}")
            asyncio.sleep(1)


@strawberry.type
class Query:
    @strawberry.field(graphql_type=User)
    def user(self, id: strawberry.ID) -> User | None:
        cur = db_conn.execute(
            "SELECT id, name, email FROM users WHERE id=?", (int(id),)
        )
        row = cur.fetchone()
        if row:
            return User(id=strawberry.ID(str(row[0])), name=row[1], email=row[2])
        return None

    @strawberry.field(graphql_type=list[User])
    def users(self) -> list[User]:
        cur = db_conn.execute("SELECT id, name, email FROM users")
        rows = cur.fetchall()
        return [User(id=strawberry.ID(str(r[0])), name=r[1], email=r[2]) for r in rows]

    @strawberry.field(graphql_type=Post)
    def post(self, id: strawberry.ID) -> Post | None:
        cur = db_conn.execute(
            "SELECT id, title, content, author_id FROM posts WHERE id=?", (int(id),)
        )
        row = cur.fetchone()
        if row:
            return Post(
                id=strawberry.ID(str(row[0])),
                title=row[1],
                content=row[2],
                author_id=strawberry.ID(str(row[3])),
            )
        return None

    @strawberry.field(graphql_type=list[Post])
    def posts(self) -> list[Post]:
        cur = db_conn.execute("SELECT id, title, content, author_id FROM posts")
        rows = cur.fetchall()
        return [
            Post(
                id=strawberry.ID(str(r[0])),
                title=r[1],
                content=r[2],
                author_id=strawberry.ID(str(r[3])),
            )
            for r in rows
        ]

    @strawberry.field(graphql_type=list[Post])
    def user_posts(self, author_id: strawberry.ID) -> list[Post]:
        cur = db_conn.execute(
            "SELECT id, title, content, author_id FROM posts WHERE author_id=?",
            (int(author_id),),
        )
        rows = cur.fetchall()
        return [
            Post(
                id=strawberry.ID(str(r[0])),
                title=r[1],
                content=r[2],
                author_id=strawberry.ID(str(r[3])),
            )
            for r in rows
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str) -> User:
        cur = db_conn.execute(
            "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id, name, email",
            (name, email),
        )
        row = cur.fetchone()
        return User(id=strawberry.ID(str(row[0])), name=row[1], email=row[2])

    @strawberry.mutation
    def create_post(self, title: str, content: str, author_id: str) -> Post:
        cur = db_conn.execute(
            "INSERT INTO posts (title, content, author_id) VALUES (?, ?, ?) RETURNING id, title, content, author_id",
            (title, content, int(author_id)),
        )
        row = cur.fetchone()
        return Post(
            id=strawberry.ID(str(row[0])),
            title=row[1],
            content=row[2],
            author_id=strawberry.ID(str(row[3])),
        )

    @strawberry.mutation(graphql_type=User)
    def update_user(self, id: strawberry.ID, name: str, email: str) -> User:
        cur = db_conn.execute(
            "UPDATE users SET name=?, email=? WHERE id=? RETURNING id, name, email",
            (name, email, int(id)),
        )
        row = cur.fetchone()
        if not row:
            raise Exception("User not found")

        return User(id=strawberry.ID(str(row[0])), name=row[1], email=row[2])


@strawberry.type
class Subscription:
    @strawberry.subscription(graphql_type=User)
    async def user(self, id: strawberry.ID) -> AsyncGenerator[User, None]:
        user_id = str(id)

        # Create a queue for each user ID
        q = asyncio.Queue()
        with subscribers_lock:
            # Add it to the dict of subscribers
            subscribers.setdefault(user_id, []).append(q)

        try:
            while True:
                user = await q.get()
                yield user
        finally:
            with subscribers_lock:
                if user_id in subscribers:
                    subscribers[user_id] = [
                        x for x in subscribers[user_id] if x is not q
                    ]
                    if not subscribers[user_id]:
                        del subscribers[user_id]


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Startup: start consumer
    consumer_task = asyncio.create_task(consumer_loop())
    yield
    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

graphql_router = GraphQLRouter(schema, graphql_ide=True)
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Database setup
db_conn = apsw.Connection("/tmp/test.db")
db_conn.set_update_hook(update_hook)

db_conn.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL
)""")

db_conn.execute("""CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users(id)
)""")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="localhost",
        port=5010,
    )
