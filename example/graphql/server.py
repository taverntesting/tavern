"""Simple GraphQL test server for integration testing using SQLite and graphene"""

import json
import sqlite3

from flask import Flask, request, jsonify
from graphene import (
    ObjectType,
    String,
    ID,
    Schema,
    Field,
    List as GrapheneList,
    Mutation,
)


class User(ObjectType):
    id = ID()
    name = String()
    email = String()


class Post(ObjectType):
    id = ID()
    title = String()
    content = String()
    author_id = ID(name="authorId")


class CreateUser(Mutation):
    class Arguments:
        name = String(required=True)
        email = String(required=True)

    user = Field(lambda: User)

    def mutate(self, info, name: str, email: str):
        connection = info.context["connection"]
        cursor = connection.cursor()

        # Get the next available ID
        cursor.execute("SELECT MAX(id) FROM users")
        result = cursor.fetchone()
        new_id = 1 if result[0] is None else result[0] + 1

        cursor.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (new_id, name, email),
        )
        connection.commit()

        return CreateUser(user=User(id=str(new_id), name=name, email=email))


class CreatePost(Mutation):
    class Arguments:
        title = String(required=True)
        content = String(required=True)
        author_id = String(required=True, name="authorId")

    post = Field(lambda: Post)

    def mutate(self, info, title: str, content: str, author_id: str):
        connection = info.context["connection"]
        cursor = connection.cursor()

        # Get the next available ID
        cursor.execute("SELECT MAX(id) FROM posts")
        result = cursor.fetchone()
        new_id = 1 if result[0] is None else result[0] + 1

        cursor.execute(
            "INSERT INTO posts (id, title, content, author_id) VALUES (?, ?, ?, ?)",
            (new_id, title, content, author_id),
        )
        connection.commit()

        return CreatePost(
            post=Post(id=str(new_id), title=title, content=content, author_id=author_id)
        )


class Query(ObjectType):
    user = Field(User, id=ID(required=True))
    users = GrapheneList(User)
    posts = GrapheneList(Post)
    user_posts = GrapheneList(Post, author_id=ID(required=True), name="userPosts")

    def resolve_user(self, info, id: str) -> User | None:
        connection = info.context["connection"]
        cursor = connection.cursor()
        cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            return User(id=str(row[0]), name=row[1], email=row[2])
        else:
            # In the original implementation, when a user wasn't found, it returned an error
            # We'll return None which should be handled by the GraphQL execution to return null
            return None

    def resolve_users(self, info) -> list[User]:
        connection = info.context["connection"]
        cursor = connection.cursor()
        cursor.execute("SELECT id, name, email FROM users")
        rows = cursor.fetchall()
        return [User(id=str(row[0]), name=row[1], email=row[2]) for row in rows]

    def resolve_posts(self, info) -> list[Post]:
        connection = info.context["connection"]
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, content, author_id FROM posts")
        rows = cursor.fetchall()
        return [
            Post(id=str(row[0]), title=row[1], content=row[2], author_id=row[3])
            for row in rows
        ]

    def resolve_user_posts(self, info, author_id: str) -> list[Post]:
        connection = info.context["connection"]
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, title, content, author_id FROM posts WHERE author_id = ?",
            (author_id,),
        )
        rows = cursor.fetchall()
        return [
            Post(id=str(row[0]), title=row[1], content=row[2], author_id=row[3])
            for row in rows
        ]


class Mutation(ObjectType):
    create_user = CreateUser.Field()
    create_post = CreatePost.Field()


schema = Schema(query=Query, mutation=Mutation)


def init_db():
    """Initialize the SQLite database with sample data"""
    conn = sqlite3.connect("/tmp/graphql_test.db")
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    # Create posts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
    """)

    # Insert sample users if they don't exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (1, "John Doe", "john@example.com"),
        )
        cursor.execute(
            "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            (2, "Jane Smith", "jane@example.com"),
        )

    # Insert sample posts if they don't exist
    cursor.execute("SELECT COUNT(*) FROM posts")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO posts (id, title, content, author_id) VALUES (?, ?, ?, ?)",
            (1, "First Post", "Hello World!", 1),
        )
        cursor.execute(
            "INSERT INTO posts (id, title, content, author_id) VALUES (?, ?, ?, ?)",
            (2, "Second Post", "GraphQL is cool", 2),
        )

    conn.commit()
    conn.close()


app = Flask(__name__)

# Initialize the database
init_db()


def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect("/tmp/graphql_test.db")
    conn.row_factory = sqlite3.Row  # This allows us to access columns by name
    return conn


@app.route("/graphql", methods=["GET", "POST"])
def graphql():
    """GraphQL endpoint with custom context"""

    def context():
        return {"connection": get_db_connection()}

    # Use GraphQLView to handle GraphQL requests
    # We'll create a custom view to handle both GET and POST
    if request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return jsonify({"errors": [{"message": "No JSON data provided"}]}), 400

            query = data.get("query")
            variables = data.get("variables", {})

            if not query:
                return jsonify({"errors": [{"message": "No query provided"}]}), 400

            result = schema.execute(
                query,
                variable_values=variables,
                context={"connection": get_db_connection()},
            )

            response_data = {}
            if result.data:
                response_data["data"] = result.data
            if result.errors:
                response_data["errors"] = [
                    {"message": str(error)} for error in result.errors
                ]

            # Return 400 if there are errors and no data
            if result.errors and not result.data:
                return jsonify(response_data), 400

            return jsonify(response_data)

        except Exception as e:
            return jsonify({"errors": [{"message": str(e)}]}), 500

    # Handle GET requests for simple queries
    else:
        try:
            query = request.args.get("query")
            variables_str = request.args.get("variables", "{}")

            if not query:
                return jsonify({"errors": [{"message": "No query provided"}]}), 400

            try:
                variables = json.loads(variables_str) if variables_str else {}
            except json.JSONDecodeError:
                variables = {}

            result = schema.execute(
                query,
                variable_values=variables,
                context={"connection": get_db_connection()},
            )

            response_data = {}
            if result.data:
                response_data["data"] = result.data
            if result.errors:
                response_data["errors"] = [
                    {"message": str(error)} for error in result.errors
                ]

            # Return 400 if there are errors and no data
            if result.errors and not result.data:
                return jsonify(response_data), 400

            return jsonify(response_data)

        except Exception as e:
            return jsonify({"errors": [{"message": str(e)}]}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="localhost", port=8001, debug=True)
