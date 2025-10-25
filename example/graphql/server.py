"""Simple GraphQL test server for integration testing"""

import json
from flask import Flask, request, jsonify

app = Flask(__name__)


class GraphQLTestServer:
    """Simple GraphQL test server implementation without external dependencies"""

    def __init__(self):
        # In-memory data store for testing
        self.users = {
            "1": {"id": "1", "name": "John Doe", "email": "john@example.com"},
            "2": {"id": "2", "name": "Jane Smith", "email": "jane@example.com"},
        }
        self.posts = [
            {
                "id": "1",
                "title": "First Post",
                "content": "Hello World!",
                "authorId": "1",
            },
            {
                "id": "2",
                "title": "Second Post",
                "content": "GraphQL is cool",
                "authorId": "2",
            },
        ]

    def resolve_user(self, id: str):
        """Resolve user by ID"""
        return self.users.get(id)

    def resolve_users(self):
        """Resolve all users"""
        return list(self.users.values())

    def resolve_posts(self):
        """Resolve all posts"""
        return self.posts

    def resolve_user_posts(self, author_id: str):
        """Resolve posts by author"""
        return [post for post in self.posts if post["authorId"] == author_id]

    def execute_query(self, query: str, variables: dict = None):
        """Execute GraphQL query"""
        variables = variables or {}

        # Simple query parsing for test purposes
        query_lower = query.lower()

        # Handle getUser query
        if "getuser" in query_lower:
            user_id = variables.get("id", "1")
            user = self.resolve_user(user_id)
            if user:
                return {"data": {"user": user}}
            else:
                return {
                    "data": {"user": None},
                    "errors": [{"message": "User not found"}],
                }

        # Handle getUsers query
        elif "getusers" in query_lower:
            users = self.resolve_users()
            return {"data": {"users": users}}

        # Handle getPosts query
        elif "getposts" in query_lower:
            posts = self.resolve_posts()
            return {"data": {"posts": posts}}

        # Handle getUserPosts query
        elif "getuserposts" in query_lower:
            author_id = variables.get("authorId", "1")
            posts = self.resolve_user_posts(author_id)
            return {"data": {"posts": posts}}

        # Handle createUser mutation
        elif "createuser" in query_lower:
            name = variables.get("name", "Test User")
            email = variables.get("email", "test@example.com")
            new_id = str(max(int(uid) for uid in self.users.keys()) + 1)
            new_user = {"id": new_id, "name": name, "email": email}
            self.users[new_id] = new_user
            return {"data": {"createUser": new_user}}

        # Handle createPost mutation
        elif "createpost" in query_lower:
            title = variables.get("title", "Test Post")
            content = variables.get("content", "Test content")
            author_id = variables.get("authorId", "1")
            new_id = str(max(int(pid) for pid in [p["id"] for p in self.posts]) + 1)
            new_post = {
                "id": new_id,
                "title": title,
                "content": content,
                "authorId": author_id,
            }
            self.posts.append(new_post)
            return {"data": {"createPost": new_post}}

        # Handle invalid query
        else:
            return {
                "errors": [
                    {
                        "message": "Unknown query",
                        "locations": [{"line": 1, "column": 1}],
                    }
                ]
            }


# Create test server instance
test_server = GraphQLTestServer()


@app.route("/graphql", methods=["POST"])
def graphql():
    """GraphQL endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"errors": [{"message": "No JSON data provided"}]}), 400

        query = data.get("query")
        variables = data.get("variables", {})

        if not query:
            return jsonify({"errors": [{"message": "No query provided"}]}), 400

        result = test_server.execute_query(query, variables)

        # Check if there are errors
        if "errors" in result and not result.get("data"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({"errors": [{"message": str(e)}]}), 500


@app.route("/graphql", methods=["GET"])
def graphql_get():
    """GraphQL GET endpoint for simple queries"""
    try:
        query = request.args.get("query")
        variables_str = request.args.get("variables", "{}")

        if not query:
            return jsonify({"errors": [{"message": "No query provided"}]}), 400

        try:
            variables = json.loads(variables_str) if variables_str else {}
        except json.JSONDecodeError:
            variables = {}

        result = test_server.execute_query(query, variables)

        # Check if there are errors
        if "errors" in result and not result.get("data"):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({"errors": [{"message": str(e)}]}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="localhost", port=8001, debug=True)
