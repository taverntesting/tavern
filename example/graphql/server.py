"""Simple GraphQL test server for integration testing using SQLite and strawberry-graphql"""

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import strawberry
from strawberry.flask.views import GraphQLView
from strawberry_sqlalchemy_mapper import (
    StrawberrySQLAlchemyMapper,
    StrawberrySQLAlchemyLoader,
)

strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

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


@strawberry_sqlalchemy_mapper.type(User)
class UserType:
    pass


@strawberry_sqlalchemy_mapper.type(Post)
class PostType:
    pass


@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: int) -> UserType | None:
        return User.query.get(id)

    @strawberry.field
    def users(self) -> list[UserType]:
        return User.query.all()

    @strawberry.field
    def posts(self) -> list[PostType]:
        return Post.query.all()

    @strawberry.field
    def user_posts(self, author_id: int) -> list[PostType]:
        return Post.query.filter_by(author_id=author_id).all()


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str) -> UserType:
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return user

    @strawberry.mutation
    def create_post(self, title: str, content: str, author_id: str) -> PostType:
        post = Post(title=title, content=content, author_id=author_id)
        db.session.add(post)
        db.session.commit()
        return post


# context is expected to have an instance of StrawberrySQLAlchemyLoader
class CustomGraphQLView(GraphQLView):
    def get_context(self):
        return {
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=db),
        }


strawberry_sqlalchemy_mapper.finalize()
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)

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
        schema=schema,
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
