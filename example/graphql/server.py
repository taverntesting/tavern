"""Simple GraphQL test server for integration testing using SQLite and graphene-sqlalchemy"""

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
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
from graphene_sqlalchemy import SQLAlchemyObjectType
from graphql import GraphQLResolveInfo
from graphql_server.flask.views import GraphQLView

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Relationship
    author = db.relationship("User", backref="posts")


class UserObject(SQLAlchemyObjectType):
    class Meta:
        model = User
        load_instance = True


class PostObject(SQLAlchemyObjectType):
    class Meta:
        model = Post
        load_instance = True


class CreateUser(Mutation):
    class Arguments:
        name = String(required=True)
        email = String(required=True)

    user = Field(lambda: UserObject)

    def mutate(self, info: GraphQLResolveInfo, name: str, email: str):
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()

        return CreateUser(user=user)


class CreatePost(Mutation):
    class Arguments:
        title = String(required=True)
        content = String(required=True)
        author_id = String(required=True, name="authorId")

    post = Field(lambda: PostObject)

    def mutate(
        self, info: GraphQLResolveInfo, title: str, content: str, author_id: str
    ):
        post = Post(title=title, content=content, author_id=author_id)
        db.session.add(post)
        db.session.commit()

        return CreatePost(post=post)


class Query(ObjectType):
    user = Field(UserObject, id=ID(required=True))
    users = GrapheneList(UserObject)
    posts = GrapheneList(PostObject)
    user_posts = GrapheneList(PostObject, author_id=ID(required=True), name="userPosts")

    def resolve_user(self, info: GraphQLResolveInfo, id: str) -> User | None:
        return User.query.get(id)

    def resolve_users(self, info) -> list[User]:
        return User.query.all()

    def resolve_posts(self, info) -> list[Post]:
        return Post.query.all()

    def resolve_user_posts(
        self, info: GraphQLResolveInfo, author_id: str
    ) -> list[Post]:
        return Post.query.filter_by(author_id=author_id).all()


class Mutation(ObjectType):
    create_user = CreateUser.Field()
    create_post = CreatePost.Field()


schema = Schema(query=Query, mutation=Mutation)

app = Flask(__name__)
# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database with the app
db.init_app(app)

app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql",
        schema=schema.graphql_schema,
        graphiql=True,  # for having the GraphiQL interface
        # Add context with the database session
        get_context=lambda: {"session": db.session},
    ),
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="localhost", port=8001, debug=True)
