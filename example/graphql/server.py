"""Simple GraphQL test server for integration testing using SQLite and graphene"""

from flask import Flask, jsonify
from graphene import (
    ID,
    Field,
    Mutation,
    ObjectType,
    Schema,
    String,
)
from graphene import (
    List as GrapheneList,
)
from graphql import GraphQLResolveInfo
from graphql_server.flask.views import GraphQLView


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

    def mutate(self, info: GraphQLResolveInfo, name: str, email: str):
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

    def mutate(
        self, info: GraphQLResolveInfo, title: str, content: str, author_id: str
    ):
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

    def resolve_user(self, info: GraphQLResolveInfo, id: str) -> User | None:
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

    def resolve_user_posts(
        self, info: GraphQLResolveInfo, author_id: str
    ) -> list[Post]:
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

app = Flask(__name__)
app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql",
        schema=schema.graphql_schema,
        graphiql=True,  # for having the GraphiQL interface
    ),
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="localhost", port=8001, debug=True)
